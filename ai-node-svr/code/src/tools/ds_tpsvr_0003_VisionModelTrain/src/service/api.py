from fastapi import APIRouter
from .task_manager import TaskManager

router = APIRouter()
task_manager = TaskManager()

@router.post("/start_task")
def start_task(param: dict):
    task_id, output = task_manager.start_task(param)
    return {
        "code": 200,
        "msg": "任务开始成功",
        "data": {"task_id": task_id, **output}
    }

@router.post("/get_result")
def get_result(param: dict):
    return {
        "code": 200,
        "msg": "结果查询成功",
        "data": task_manager.get_result(param.get("task_id"))
    }

@router.post("/list_tasks")
def list_tasks():
    return {
        "code": 200,
        "msg": "任务列表查询成功",
        "data": task_manager.list_tasks()
    }

@router.post("/stop_task")
def stop_task(param: dict):
    return {
        "code": 200,
        "msg": "任务结束并删除成功",
        "data": task_manager.stop_task(param.get("task_id"))
    }