"""数据登记检查、AI 助手页（原 main() 中的两段）。"""
from checks import data_agent_checks


def test_data_agent(app, w):
    data_agent_checks(app, w)
