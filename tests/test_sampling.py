from acceptance_ext.normalization.sampling import parse_sampling_rule, sampling_script


def test_all_sampling():
    rule = parse_sampling_rule("全数检查。")
    assert rule.kind == "explicit_quantity"
    assert rule.branches[0].mode == "all"
    assert sampling_script(rule) == "ALL()"


def test_rate_and_minimum_sampling():
    rule = parse_sampling_rule("在同一检验批内，抽查构件数量的10%，且不应少于3件。")
    assert rule.kind == "explicit_quantity"
    branch = rule.branches[0]
    assert branch.rate_percent == 10
    assert branch.minimum == 3
    assert branch.unit == "件"


def test_multi_object_sampling():
    rule = parse_sampling_rule(
        "在同一检验批内，对梁应抽查构件数量的10%，且不应少于3件；"
        "对板应抽查10%，且不应少于3间。"
    )
    assert len(rule.branches) == 2
    assert rule.branches[0].object_name == "梁"
    assert rule.branches[1].object_name == "板"
