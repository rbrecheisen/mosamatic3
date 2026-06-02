# Mosamatic3

## Running the app without Docker
- scripts\rundockerbackendservices.ps1 (Redis and Celery)
- from mosamatic3\server
  - fastapi dev app\main.py
- from mosamatic3\ui
  - npm dev run

## Running the app with Docker
- scripts\rundockerall.ps1


## Adding new tasks

### Server
- In mosamatic3\server\app\processing\tasks create a new folder <task name>
- Create an empty __init__.py file in there
- Create a new file <task name>.py
- Create a new file <task name>task.py

  ```
  ...
  from app.processing.tasks.<task name>.<task name> import run_task

  @celery_app.task(bind=True, name="app.processing.tasks.<task name>.<task name>")
  def <task name>task(self, parameter_a: str, parameter_b: int) -> dict[str, Any]:
    ...
  ```

- Update file <task name>.py as follows:

  ```
  def run_task(parameter_a: str, parameter_b: str) -> None:
    print(f"parameter_a: {parameter_a}, parameter_b: {parameter_b}")
  ```

- Update file mosamatic3\server\app\processing\app.py

  ```
  ...
  include=[
    ...,
    "app.processing.tasks.<task name>.<task name>task",
  ],
  ```

- Update file mosamatic3\server\app\services\taskservice.py

  ```
  def start_<task name>task(
      parameter_a: str,
      parameter_b: str,
  ) -> dict[str, str]:
      task = <task name>task.delay(
          parameter_a=parameter_a,
          parameter_b=parameter_b,
      )
      return {"task_id": task.id, "status": "queued"}

  def validate_task_parameters(task_key: str, parameters: dict[str, Any]) -> dict[str, Any]:
    ...
    if task_key == "<task name>":
      parameter_a = parameters.get("parameter_a", "")
      parameter_b = parameters.get("parameter_b", "")
      if parameter_a != "x":
        raise HTTPException(
          status_code=HTTP_422_UNPROCESSABLE_ENTITY,
          detail="Parameter 'parameter_a' has an illegal value.",
        )
      if parameter_b != "x":
        ...
      return {
        "parameter_a": parameter_a,
        "parameter_b": parameter_b,
      }
    ...
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail=f"Unknown task: {task_key}",
    )

  def start_task_by_key(task_key: str, current_user: User, session: Session) -> dict[str, str]:
    ...
    parameters = validate_task_parameters(task_key, saved.parameters)
    ...
    if task_key == "<task name>":
      return start_<task name>task(
        parameter_a=parameters["parameter_a"],
        parameter_b=parameters["parameter_b"],
      )
  ```

### UI
- Update mosamatic3\ui\src\app\pages\analysis\analysispage.tsx

  ```
  ...
  const AVAILABLE_TASKS: AvailableTask[] = [
    ...,
    {
      id: "<task name>",
      name: "<task display name>",
    }
  ];
  ...
  ```

- Update mosamatic3\ui\src\app\pages\analysis\taskparameterspage.tsx

  ```
  ...
  const TASK_NAMES: Record<string, string> = {
    ...
    <task name>: "<task description>",
  };
  ...
  export function TaskParametersPage() {
    const { taskKey } = useParams();
    const navigate = useNavigate();
    ...
    const [parameterA, setParameterA] = useState(""); // or other default
    const [parameterB, setParameterB] = useState("");
    ...
    useEffect(() => {
      ...
      async function loadSavedParameters() {
        ...
        try {
          ...
          const savedParameterA = savedParameters.parameters.parameter_a; // or parameterA
          const savedParameterB = savedParameters.parameters.parameter_b;
          if (typeof savedParameterA === 'string') {
            setParameterA(savedParameterA);
          }
          if (typeof savedParameterB === 'string') {
            setParameterB(savedParameterB);
          }
        }
        ...
      }
      ...
    }

    async function handleSubmit(event: FormEvent<HTMLFormElement>) {
      ...
      if (resolvedTaskKey === "<task name>") {
        parameters = {
          parameterA: parameterA, // declared at top of function
          parameterB: parameterB,
        }
      }
      ...
    }

      return (
        <section className="card stack">
          ...
          {loading ? (
            <p className="muted">Loading parameters...</p>
          ) : (
            <form className="stack" onSubmit={handleSubmit}>
              ...
              {resolvedTaskKey === "<task name>" && (
                <label>
                  Parameter A
                  <input
                    type="text"
                    value={parameterA}
                    onChange={(event) => setParameterA(event.target.value)}
                    required
                  />
                </label>
                <label>
                  Parameter B
                  <select
                    value={parameterB}
                    onChange={(event) => setParameterB(event.target.value)}
                  >
                    <option value="x">x</option>
                    <option value="y">y</option>
                  </select>
                </label>
              )}
              ...                
            </form>
          )}
        </section>
      );
  ```