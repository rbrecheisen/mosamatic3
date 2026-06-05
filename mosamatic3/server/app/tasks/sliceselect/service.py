import time
from typing import Any
from celery.exceptions import Ignore
from app.utils import load_dicom
from app.tasks.runtime import TaskRuntime
from app.services.datasetservice import OutputDatasetFile
from app.tasks.sliceselect.schema import SliceSelectTaskParameters

# CHECK SUGGESTIONS HERE!!!
# https://chatgpt.com/g/g-p-69fc389d9e648191ad8b176192d732cf-mosamatic3/c/6a22bb65-a6ac-8391-ba5e-c43f0b6f7512

def process_dicom_file(file_path, relative_path: str, target_size: int) -> OutputDatasetFile | None:
  return ""


def run_sliceselect(
  parameters: dict,
  user_id: str,
  celery_task: Any | None = None,
) -> dict:
  
  # Create new task runtime
  runtime = TaskRuntime(
    task_key="sliceselect",
    parameters=parameters,
    parameter_model=SliceSelectTaskParameters,
    user_id=user_id,
    celery_task=celery_task,
  )

  # Get runtime parameters and values
  params = runtime.params

  # Mark task as running
  runtime.mark_running()

  try:

    # Get input dataset and total file count
    dataset = runtime.get_input_dataset(params.dataset_id)
    total = dataset.file_count

    # Update runtime progress to start at zero
    runtime.update_progress(
      current=0,
      total=total,
      message="Starting slice selection",
    )

    # Create empty output file list
    output_files: list[OutputDatasetFile] = []

    # Run through the list of input files
    for item in runtime.iter_dataset_files(
      dataset,
      message_factory=lambda current, total: (
        f"Selecting slice in scan {current} of {total}"
      ),
    ):
      
      # Process the current input file and add its result to the output list
      output_file = process_dicom_file(
        file_path=item.path,
        relative_path=item.file.relative_path,
        target_size=params.target_size,
      )
      if output_file is not None:
        output_files.append(output_file)
      time.sleep(0.05)

    # Create new output dataset with the output files
    output_dataset = runtime.create_output_dataset(
      name="Slice Select Task output",
      files=output_files,
    )

    # Update runtime progress to finish
    runtime.update_progress(
      current=total,
      total=total,
      message="Finished slice selection",
    )

    # Mark task status as finished
    runtime.mark_finished()

    # Return task result meta data
    return {
      "current": total,
      "total": total,
      "message": "Slice select task completed",
      "parameters": params.model_dump(mode="json"),
      "output_datasets": [
        output_dataset.model_dump(mode="json"),
      ],
    }
  except Ignore:
    raise
  except Exception:
    runtime.mark_failed()
    raise