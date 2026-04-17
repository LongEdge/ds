import uuid
import threading
from ..process.proc_img_train import CWrinkleImgTrain

class TaskManager:
    def __init__(self):
        self.tasks = {}  # {task_id: {"status":..., "logs":[], "result":...}}

    def start_task(self, param: dict):
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            "status": "running",
            "logs": [],
            "result": None
        }

        # # 后台线程执行训练
        # threading.Thread(
        #     target=self._run_training, args=(task_id, param), daemon=True
        # ).start()
        self._run_training(task_id,param)
        return task_id, {"status": "submitted"}

    def _run_training(self, task_id, param):
        try:
            trainer = CWrinkleImgTrain(process_comm=None)
            self.tasks[task_id]["logs"].append("开始训练任务...")
            trainer.trainImgModuleByUnetIteratorFalingwen(
                image_dirs=param["image_dirs"],
                mask_dirs=param["mask_dirs"],
                model_dir=param["model_dir"],
                model_name=param["model_name"],
                model_pretrain_path=param.get("pretrain_path"),
                model_checkpoint_path=param.get("checkpoint_path"),
                model_dataset_name=param.get("dataset_name", "WrinkleDatasetFlip"),
                epochs=param.get("epochs", 50),
                batch_size=param.get("batch_size", 4),
                lr=param.get("lr", 1e-4),
                gpu_id=param.get("gpu_id", 0),
            )
            self.tasks[task_id]["status"] = "finished"
            self.tasks[task_id]["logs"].append("训练完成 ✅")
        except Exception as e:
            self.tasks[task_id]["status"] = "error"
            self.tasks[task_id]["logs"].append(f"训练失败: {str(e)}")

    def get_result(self, task_id):
        return self.tasks.get(task_id, {})

    def list_tasks(self):
        return self.tasks

    def stop_task(self, task_id):
        # 简化实现：标记为 stopped
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "stopped"
        return self.tasks.get(task_id, {})