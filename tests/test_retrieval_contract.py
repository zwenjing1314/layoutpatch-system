import pytest
import torch

from backend.algorithms.contracts import maxsim_scores, top_k, unpad_query, valid_embedding


def test_attention_keeps_real_augmentation_and_drops_only_masked_padding():
    vectors = torch.zeros(4, 128)
    vectors[0, 0] = vectors[1, 1] = vectors[2, 2] = 1
    # The third row may have tokenizer pad ID, but attention=1 makes it real.
    result = unpad_query(vectors, torch.tensor([1, 1, 1, 0]))
    assert result.shape == (3, 128)
    vectors[3, 3] = 1
    with pytest.raises(ValueError, match="exactly zero"):
        unpad_query(vectors, torch.tensor([1, 1, 1, 0]))


def test_maxsim_preserves_all_page_tokens_and_ranks_by_query_coverage():
    query = torch.eye(128)[:2]
    both = torch.eye(128)[0].repeat(1031, 1)
    both[-1] = query[1]  # Prompt vector contributes to full-page retrieval.
    one = torch.eye(128)[0].repeat(1031, 1)
    scores = maxsim_scores(query, [one, both])
    torch.testing.assert_close(scores, torch.tensor([1.0, 2.0]))
    assert [h.page_id for h in top_k(["one", "both"], scores, 2)] == ["both", "one"]


def test_duplicate_ids_nonfinite_scores_and_compressed_pages_fail_closed():
    with pytest.raises(ValueError, match="Unique"):
        top_k(["same", "same"], torch.ones(2), 2)
    with pytest.raises(ValueError, match="finite"):
        top_k(["p"], torch.tensor([float("nan")]), 1)
    with pytest.raises(ValueError, match="1031"):
        valid_embedding(torch.eye(128), rows=1031)
    assert top_k([], torch.empty(0), 1) == []


def test_top_k_ties_are_stable_and_k_cannot_expand_without_bound():
    assert [h.page_id for h in top_k(["b", "a"], torch.ones(2), 2)] == ["a", "b"]
    with pytest.raises(ValueError, match="k must"):
        top_k(["a"], torch.ones(1), 0)
