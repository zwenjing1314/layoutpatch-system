"""Small explicit REST adapter for Qdrant's exact multivector query API."""
import math
import re
import httpx

from .settings import SearchSettings, qdrant_key


class SearchUnavailable(RuntimeError):
    pass


def validate_vector(vector, rows=None):
    if not isinstance(vector, list) or not vector or (rows is not None and len(vector) != rows) or len(vector) > 4096:
        raise SearchUnavailable("Invalid embedding shape")
    for row in vector:
        if not isinstance(row, list) or len(row) != 128:
            raise SearchUnavailable("Invalid embedding dimension")
        if any(type(x) not in (float, int) or not math.isfinite(x) for x in row):
            raise SearchUnavailable("Invalid embedding values")
        if abs(math.sqrt(sum(x*x for x in row))-1) >= .03:
            raise SearchUnavailable("Invalid embedding normalization")
    return vector


class Qdrant:
    def __init__(self, settings=None):
        self.settings = settings or SearchSettings.from_environment()

    def request(self, method, path, body=None, missing=False):
        try:
            with httpx.Client(base_url=self.settings.qdrant_url, headers={"api-key": qdrant_key()},
                              timeout=30, trust_env=False) as client:
                response = client.request(method, path, json=body)
            if missing and response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "ok":
                raise ValueError("Qdrant operation failed")
            return data["result"]
        except (httpx.HTTPError, ValueError, KeyError, OSError) as error:
            raise SearchUnavailable("Qdrant unavailable or invalid response") from None

    @staticmethod
    def path(collection):
        if not re.fullmatch(r"layoutpatch_system_[a-z0-9_]+", collection):
            raise SearchUnavailable("Unexpected collection identity")
        return "/collections/" + collection

    def info(self, collection):
        return self.request("GET", self.path(collection), missing=True)

    def create(self, collection):
        return self.request("PUT", self.path(collection), {
            "vectors": {"original": {"size": 128, "distance": "Dot", "datatype": "float32",
                "multivector_config": {"comparator": "max_sim"}, "hnsw_config": {"m": 0}}},
            "optimizers_config": {"indexing_threshold": 0}})

    @staticmethod
    def check_info(info, count=None):
        try:
            config = info["config"]
            vectors = config["params"]["vectors"]
            v = vectors["original"]
            if (set(vectors) != {"original"} or v["size"] != 128 or v["distance"] != "Dot"
                or v["multivector_config"]["comparator"] != "max_sim"
                or v.get("datatype", "float32") != "float32" or v.get("hnsw_config", {}).get("m") != 0
                or config.get("quantization_config") is not None or v.get("quantization_config") is not None
                or (count is not None and info["points_count"] != count)):
                raise ValueError()
        except (TypeError, KeyError, ValueError):
            raise SearchUnavailable("Index configuration/count mismatch") from None

    def upsert(self, collection, points):
        self.request("PUT", self.path(collection) + "/points?wait=true", {"points": points})

    def delete_points(self, collection, point_ids):
        if point_ids:
            self.request("POST", self.path(collection) + "/points/delete?wait=true", {"points": point_ids})

    def all_points(self, collection):
        result, offset = [], None
        while True:
            body = {"limit": 64, "with_payload": True, "with_vector": True}
            if offset is not None:
                body["offset"] = offset
            data = self.request("POST", self.path(collection) + "/points/scroll", body)
            result.extend(data["points"])
            offset = data.get("next_page_offset")
            if offset is None:
                return result
            if len(result) > 10000:
                raise SearchUnavailable("Unexpected index size")

    def query(self, scope, vector, k):
        if not scope.pages:
            raise ValueError("Empty scope must short-circuit before Qdrant")
        validate_vector(vector)
        self.check_info(self.info(scope.collection), scope.index_page_count)
        body = {"query": vector, "using": "original", "limit": k,
                "params": {"exact": True}, "with_payload": True, "with_vector": False,
                "filter": {"must": [
                    {"key": "document_version_id", "match": {"any": sorted({p.version_id for p in scope.pages})}},
                    {"key": "profile_id", "match": {"value": scope.profile_id}},
                    {"key": "index_generation", "match": {"value": scope.index_id}},
                    {"has_id": [p.id for p in scope.pages]}]}}
        data = self.request("POST", self.path(scope.collection) + "/points/query", body)
        try:
            if not isinstance(data["points"], list):
                raise ValueError()
            return data["points"]
        except (TypeError, KeyError, ValueError):
            raise SearchUnavailable("Invalid search response") from None
