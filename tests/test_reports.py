from app.services import demo_data_service, report_service


def test_report_builds_and_renders(user):
    demo_data_service.load_demo_data(user.id, months=6)
    report = report_service.build_report(user.id, "Test <User>", "3M")
    assert report.has_data and report.summary["income"] > 0
    html = report_service.render_html(report)
    assert "Financial summary" in html and "not financial advice" in html
    assert "<User>" not in html and "&lt;User&gt;" in html  # user text is escaped


def test_empty_report(user):
    report = report_service.build_report(user.id, "Test", "ALL")
    assert not report.has_data
