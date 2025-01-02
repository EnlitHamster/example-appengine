from flask import Flask, Response, request

from google.cloud import tasks_v2
from google.cloud.tasks_v2 import Task


ALLOWED_QUEUES = ('task-queue', )


app = Flask(__name__)


# the minimal Flask application
@app.route('/')
def index():
    return '<h1>Hello, World!</h1>'


# bind multiple URL for one view function
@app.route('/hi')
@app.route('/hello')
def say_hello():
    return '<h1>Hello, Flask!</h1>'


# dynamic route, URL variable default
@app.route('/greet', defaults={'name': 'Programmer'})
@app.route('/greet/<name>')
def greet(name):
    create_app_engine_task('/task/greeted', name, 'task-queue')
    return f'<h1>Hello, {name}!</h1>'


@app.route('/task/greeted')
def greeted_task():
    queue_name = request.headers.get('X-Appengine-Queuename')
    if queue_name is None or queue_name not in ALLOWED_QUEUES:
        return Response('Only Cloud Tasks can call this route', status=401)

    name = request.data.decode('utf-8')
    print(f'Greeted {name}')
    return Response(status=204)


def create_app_engine_task(relative_url: str, payload: str, queue_name: str) -> Task:
    client = tasks_v2.CloudTasksClient()

    # Create the parent queue name
    parent = client.queue_path('playground-tofu-project', 'europe-west1', queue_name)

    task: dict = {
        "app_engine_http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "relative_uri": relative_url,
            "body": payload.encode('utf-8'),
            "app_engine_routing": {
                "version": "production",
            },
        }
    }

    # Create the task request
    task_request = {
        "parent": parent,
        "task": task
    }

    # Send the task creation request
    return client.create_task(request=task_request)
