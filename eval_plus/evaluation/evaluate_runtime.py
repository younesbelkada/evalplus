import multiprocessing
from math import sqrt
from typing import Any, List, Union

from eval_plus.evaluation.evaluate import construct_inputs_sig
from eval_plus.evaluation.evaluate_helpers import (
    TimeoutException,
    create_tempdir,
    reliability_guard,
    swallow_io,
    time_limit,
)
from eval_plus.utils import get_human_eval_plus


def execute_for_runtime(code: str, inputs: List, signature: str) -> str:
    eval_code = code + f"\noutputs = {signature}({construct_inputs_sig(inputs)})"

    def unsafe_execute():
        with create_tempdir():
            # These system calls are needed when cleaning up tempdir.
            import os
            import shutil

            rmtree = shutil.rmtree
            rmdir = os.rmdir
            chdir = os.chdir
            # Disable functionalities that can make destructive changes to the test.
            reliability_guard()
            # Construct the check program and run it.
            check_program = eval_code
            exec_global = {}
            try:
                import time

                start_time = time.time()
                with swallow_io():
                    with time_limit(1):
                        exec(check_program, exec_global)
                duration = time.time() - start_time
                result.append(duration)
            except TimeoutException:
                result.append("timed out")
            except BaseException as e:
                print(str(e))
                result.append("thrown exception")
            # Needed for cleaning up.
            shutil.rmtree = rmtree
            os.rmdir = rmdir
            os.chdir = chdir

    manager = multiprocessing.Manager()
    result = manager.list()
    p = multiprocessing.Process(target=unsafe_execute)
    p.start()
    p.join(timeout=1 + 1)
    if p.is_alive():
        p.kill()
    return result[0]


def test_solution_runtime(
    dataset: str = "humaneval",
    task_id: str = "HumanEval/0",
    impl: str = "canonical",
    inputs: Union[str, List[List[Any]]] = "base_input",
    repeat: int = 10,
):
    if "humaneval" in dataset:
        problems, problem = get_human_eval_plus(), None
        for p in problems:
            if p["task_id"] == task_id:
                problem = p
        assert problem != None, f"invalid {task_id = }"
        entry_point = problem["entry_point"]
        impl = problem["prompt"] + (
            impl if impl != "canonical" else problem["canonical_solution"]
        )
        if inputs == "base_input":
            inputs = problem["base_input"]

        results = [0, 0]
        for input_list in inputs:
            runtime_list = [
                execute_for_runtime(impl, input_list, entry_point)
                for _ in range(repeat)
            ]
            if any(type(x) != float for x in runtime_list):
                print(f"{task_id = } incorrect")
                return None, None
            avg_runtime = sum(runtime_list) / len(runtime_list)
            if avg_runtime > results[0]:
                results[0] = avg_runtime
                results[1] = sqrt(
                    sum((runtime - avg_runtime) ** 2 for runtime in runtime_list)
                    / (repeat - 1)
                )

        return results
