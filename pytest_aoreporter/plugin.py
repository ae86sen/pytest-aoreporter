import os
import random
import datetime

import pytest
from jinja2 import Template
from py._xmlgen import html

cases = []
base_dir = os.path.dirname(__file__)
base_html_path = os.path.join(base_dir, "html")


def pytest_collection_modifyitems(items):
    """
    修改用例名称中文乱码
    :param items:
    :return:
    """
    for item in items:
        item.name = item.name.encode('utf-8').decode('unicode_escape')
        item._nodeid = item.nodeid.encode('utf-8').decode('unicode_escape')


def pytest_addoption(parser):
    report = parser.getgroup("aoreporter")
    report.addoption("--ao-html",
                     action="store",
                     dest="htmlpath",
                     metavar="path",
                     default="aoreport.html",
                     help='create html report file at given path'
                     )



def parse_testcase_nodeid(nodeid) -> dict:
    test_module, test_class, test_method = nodeid.split("::")
    case_id = str(random.randint(0, 99999)) + "_" + test_method
    return {"test_class": f"{test_module}.{test_class}", "test_method": test_method, "case_id": case_id}


@pytest.mark.hookwrapper(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item):
    outcome = yield
    report = outcome.get_result()
    description = item.function.__doc__ or ''
    if report.when == "setup":
        case_basic_info = parse_testcase_nodeid(report.nodeid)
        if report.outcome == "skipped":

            result_info = {
                "logs": report.longrepr,
                "result": report.outcome,
                "duration": 0,
                "f_duration": "0.00s",
                "doc": description,
                "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            result_info.update(case_basic_info)
            cases.append(result_info)
        elif report.outcome == "failed":
            result_info = {
                "logs": report.longrepr,
                "result": 'error',
                "duration": report.duration,
                "f_duration": "%.2fs" % report.duration,
                "doc": description,
                "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            result_info.update(case_basic_info)
            cases.append(result_info)
    if report.when == 'call':
        case_basic_info = parse_testcase_nodeid(report.nodeid)
        report.nodeid = report.nodeid.encode("utf-8").decode("unicode_escape")  # 设置编码显示中文
        result_info = {
            "logs": str(report.longrepr) if report.longrepr else "",
            "result": report.outcome,
            "duration": report.duration,
            "f_duration": "%.2fs" % report.duration,
            "doc": description,
            "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        # 更新结果
        result_info.update(case_basic_info)
        cases.append(result_info)


class HtmlMaker:
    def __init__(self, report_target_path):
        self.heading_html_path = os.path.join(base_html_path, "heading.html")
        self.report_html_path = os.path.join(base_html_path, "report.html")
        self.template_html_path = os.path.join(base_html_path, "template.html")
        self.report_target_path = report_target_path

    @staticmethod
    def gen_html_to_str(html_path: str) -> str:
        """读取.html文件内容
        html_file: heading.html,report.html
        """
        # 读取heading.html内容
        with open(html_path, 'r', encoding="utf-8") as f:
            html_str = f.read()
        return html_str

    @staticmethod
    def render_html(html_str: str, render_content):
        temp = Template(html_str)
        temp_str = temp.render(render_content)
        return temp_str

    def render_template_html(self, render_content: dict):
        """将heading.html,report.html渲染到template.html"""
        template_str = self.gen_html_to_str(self.template_html_path)
        html_path_dict = {
            "heading": self.heading_html_path,
            "report": self.report_html_path,
        }
        html_rendered_dict = {}
        # 1.分别读取并渲染heading.html,report.html,stylesheet.html
        for key, html_path in html_path_dict.items():
            html_str = self.gen_html_to_str(html_path)
            rendered_html = self.render_html(html_str, render_content)
            html_rendered_dict[key] = rendered_html

        # 2.全部内容渲染到目标报告：aoreporter.html
        timestamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S_')
        report_name = timestamp + r"aoreporter.html"
        with open(os.path.join(self.report_target_path, report_name), "w", encoding='utf-8') as f:
            temp = Template(template_str)
            temp_str = temp.render(html_rendered_dict)
            f.write(temp_str)


@pytest.fixture(scope="session", autouse=True)
def gen_reports(request):
    report_name = request.config.getoption("--ao-html")
    start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    yield
    end_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if report_name:
        print("-----------测试结束, AoReporter开始收集报告-----------")
        passed_count = len(list(filter(lambda x: x["result"] == "passed", cases)))
        failed_count = len(list(filter(lambda x: x["result"] == "failed", cases)))
        skipped_count = len(list(filter(lambda x: x["result"] == "skipped", cases)))
        error_count = len(list(filter(lambda x: x["result"] == "error", cases)))
        duration = sum([case["duration"] for case in cases])
        duration = "%.2fs" % duration
        passed_rate = '{:.2%}'.format(passed_count / len(cases))
        failed_rate = '{:.2%}'.format(failed_count / len(cases))
        error_rate = '{:.2%}'.format(error_count / len(cases))
        skipped_rate = '{:.2%}'.format(skipped_count / len(cases))
        summary = {
            "total": len(cases),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "error_count": error_count,
            "skipped_count": skipped_count,
            "passed_rate": passed_rate,
            "error_rate": error_rate,
            "skipped_rate": skipped_rate,
            "failed_rate": failed_rate,
            "duration": duration,
            "start_time": start_time,
            "end_time": end_time,
            "case_list": cases
        }
        # report_path = request.config.getoption("--pytest-tmreport-path", default='.')
        html_maker = HtmlMaker(report_name)
        html_maker.render_template_html(summary)
        print(f"-----------AOReporter已完成测试报告!报告路径：{report_name}-----------")

# if __name__ == '__main__':
#     summary = {
#         "total": 18,
#         "passed_count": 3,
#         "failed_count": 4,
#         "error_count": 1,
#         "skipped_count": 10,
#         "passed_rate": "10%",
#         "error_rate": "10%",
#         "skipped_rate": "10%",
#         "failed_rate": "10%",
#         "duration": "66s",
#         "start_time": "2022-06-24 22:00:01",
#         "end_time": "2022-06-24 22:01:07",
#         "case_list": [
#             {"test_class": "test_ehpc.py.TestJob",
#              "test_method": "test_submit_ehpc_job",
#              "doc": "提交作业", "duration": 10.12212,
#              "f_duration": "10s",
#              "time": "2022-06-25 11:00:06",
#              "result": "passed",
#              "log": "asdasdada"}
#         ]
#     }
#     html_maker = HtmlMaker('.')
#     html_maker.render_template_html(summary)
