from android_lab.agent.model import *



def get_agent(agent_module: str, **kwargs) -> Agent:
    # 直接从全局命名空间中获取类
    class_ = globals().get(agent_module)

    if class_ is None:
        raise AttributeError(f"Not found class {agent_module}")

    # 检查类是否是 Agent 的子类
    if not issubclass(class_, Agent):
        raise TypeError(f"{agent_module} is not Agent")

    # 创建类的实例
    return class_(**kwargs)
