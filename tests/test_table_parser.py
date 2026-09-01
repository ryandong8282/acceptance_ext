from acceptance_ext.table_parser import extract_table_rows


def test_extract_simple_table_rows():
    html = """
    <table>
      <tr><td>项目</td><td>允许偏差(mm)</td><td>检验方法</td></tr>
      <tr><td>轴线位置</td><td>5</td><td>尺量</td></tr>
      <tr><td>表面平整度</td><td>4</td><td>靠尺量测</td></tr>
    </table>
    """
    rows = extract_table_rows(html)
    assert [row.name for row in rows] == ["轴线位置", "表面平整度"]
    assert rows[0].value == "5"
    assert rows[0].unit == "mm"
    assert rows[1].method == "靠尺量测"
