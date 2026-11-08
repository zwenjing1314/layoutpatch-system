"""Strict DocVortex 2.0 top-level candidate export to the SAME 144dpi PNG."""
import math

TYPE_MAP = {
    "text": "text", "list": "text", "index": "text", "ref_text": "text",
    "header": "text", "footer": "text", "page_number": "text", "aside_text": "text",
    "page_footnote": "text", "code": "text", "doc_title": "title", "paragraph_title": "title",
    "image": "image", "chart": "image", "table": "table", "equation": "equation",
}


class ParseError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def text_content(value):
    if isinstance(value, dict):
        if isinstance(value.get("content"), str):
            return value["content"]
        return " ".join(filter(None, (text_content(v) for k,v in value.items() if k not in {"bbox", "image_base64", "image_path"})))
    if isinstance(value, list):
        return " ".join(filter(None, map(text_content, value)))
    return ""


def finite_box(box, maximum=None):
    return (isinstance(box, list) and len(box) == 4
            and all(type(v) in (int,float) and math.isfinite(v) for v in box)
            and 0 <= box[0] < box[2] and 0 <= box[1] < box[3]
            and (maximum is None or box[2] <= maximum[0] and box[3] <= maximum[1]))


def export_candidates(payload, identity, geometry):
    if payload.get("schema") != "docvortex.middle" or payload.get("schema_version") != "2.0":
        raise ParseError("PARSER_SCHEMA_MISMATCH")
    pages = payload.get("pages", [])
    if len(pages) != 1 or pages[0].get("page_idx") != identity["page_index"]:
        raise ParseError("PARSER_PAGE_MISMATCH")
    extension = payload.get("extensions", {}).get("docvortex_layout", {})
    sizes = extension.get("pages", [])
    if extension.get("version") != 1 or len(sizes) != 1 or sizes[0].get("page_idx") != identity["page_index"]:
        raise ParseError("PARSER_GEOMETRY_MISSING")
    size = [sizes[0].get("width_pt"), sizes[0].get("height_pt")]
    expected = geometry["page_size_points"]
    if (any(type(v) not in (int,float) or not math.isfinite(v) or v <= 0 for v in size)
            or any(not math.isclose(a,b,abs_tol=0.002,rel_tol=0) for a,b in zip(size, expected))):
        raise ParseError("PARSER_GEOMETRY_MISMATCH")
    if geometry["rotation"] != 0 or geometry["cropbox"] != geometry["mediabox"] or geometry["mediabox"][:2] != [0,0]:
        raise ParseError("UNSUPPORTED_PDF_GEOMETRY")
    matrix = geometry["parser_points_to_png"]
    if len(matrix) != 6 or any(type(v) not in (int,float) or not math.isfinite(v) for v in matrix):
        raise ParseError("PARSER_GEOMETRY_MISMATCH")
    width, height = identity["width_px"], identity["height_px"]
    if geometry["width_px"] != width or geometry["height_px"] != height or geometry["render_sha256"] != identity["render_sha256"]:
        raise ParseError("RENDER_IDENTITY_MISMATCH")
    seen, candidates = set(), []
    # DocVortex Page.blocks defaults to []; its to_json skips default fields.
    # An absent field is a valid empty page. Explicit null/malformed blocks fail.
    blocks = pages[0].get("blocks", [])
    if not isinstance(blocks, list):
        raise ParseError("PARSER_SCHEMA_MISMATCH")
    for block in blocks:
        index, kind, unit = block.get("index"), block.get("type"), block.get("bbox")
        if type(index) is not int or index < 0 or index in seen:
            raise ParseError("PARSER_DUPLICATE_OR_INVALID_ID")
        if kind not in TYPE_MAP:
            raise ParseError("PARSER_UNKNOWN_TYPE")
        if not finite_box(unit, [1,1]):
            raise ParseError("PARSER_INVALID_BBOX")
        seen.add(index)
        a,b,c,d,e,f = matrix
        points = [(a*x+c*y+e,b*x+d*y+f) for x,y in ((unit[0]*size[0],unit[1]*size[1]), (unit[2]*size[0],unit[1]*size[1]), (unit[0]*size[0],unit[3]*size[1]), (unit[2]*size[0],unit[3]*size[1]))]
        box = [min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
        if not finite_box(box, [width,height]):
            raise ParseError("PARSER_BBOX_OUT_OF_BOUNDS")
        candidates.append({**identity, "candidate_id": f"{identity['page_id']}:block:{index}", "layout_id": index,
            "type": TYPE_MAP[kind], "parser_type": kind, "bbox": box, "coordinate_system": "original_png_pixel_xyxy_top_left",
            "parser_bbox_unit": unit, "text": text_content(block), "text_source": "native_PDF_or_OCR_not_disambiguated", "ocr_text": None, "vlm_text": None})
    return sorted(candidates, key=lambda c: c["layout_id"])
