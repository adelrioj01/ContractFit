from contractfit.evaluation import EvaluationCase, evaluate
from contractfit.evaluation_dataset import EVALUATION_CASES
from contractfit.sample_data import SAMPLE_PROFILE


def test_labeled_evaluation_meets_baseline() -> None:
    cases = [EvaluationCase.model_validate(item) for item in EVALUATION_CASES]
    report = evaluate(cases, SAMPLE_PROFILE)
    assert report.extraction_recall == 1
    assert report.citation_validity == 1
    assert report.eligibility_accuracy == 1
