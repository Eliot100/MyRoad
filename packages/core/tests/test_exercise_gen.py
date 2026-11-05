"""1,000 generated exercises per teaching stage: right answer, no duplicates."""

from __future__ import annotations

from myroad_core.content.exercise_gen import teaching_generators


def test_one_thousand_samples_per_stage_are_correct_and_unique() -> None:
    generators = teaching_generators()
    assert len(generators) >= 79
    for stage in generators:
        samples = stage.samples(1000)
        assert len(samples) == 1000, stage.topic_id
        seen: set[tuple] = set()
        seed_ids: set[str] = set()
        for exercise in samples:
            assert exercise.topic_id == stage.topic_id
            assert exercise.level == stage.level
            assert exercise.level in (1, 2, 3)
            assert exercise.answer in exercise.choices
            assert len(exercise.choices) == len(set(exercise.choices))
            assert exercise.distractors
            assert stage.recompute(exercise) == exercise.answer
            assert stage.check(exercise, exercise.answer)
            for wrong in exercise.distractors:
                assert not stage.check(exercise, wrong)
            key = (exercise.prompt, exercise.choices, exercise.answer)
            assert key not in seen, stage.topic_id
            seen.add(key)
            kind = exercise.parameters[0]
            if kind == "seed":
                seed_ids.add(exercise.parameters[1])
            elif kind == "span":
                assert exercise.answer in stage.source
                for wrong in exercise.distractors:
                    assert wrong not in stage.source
            elif kind == "order" and exercise.parameters[1][0] == "span":
                assert exercise.answer in stage.source
                for wrong in exercise.distractors:
                    assert wrong not in stage.source
            elif kind == "cloze":
                prefix, post = exercise.parameters[1], exercise.parameters[2]
                assert exercise.prompt == f"{prefix} ___ {post}"
                assert stage._answer_for_prefix[prefix] == exercise.answer
        if stage._seeds:
            assert samples[0].parameters[0] == "seed"
            assert seed_ids
