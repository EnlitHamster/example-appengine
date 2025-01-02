import os
from flask import Flask, Response, request
from datetime import datetime

from google.cloud import tasks_v2
from google.cloud.tasks_v2 import Task
import sqlalchemy as sa

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from sqlalchemy.types import DateTime, String


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


class Base(DeclarativeBase):
    pass


class Greeting(Base):
    __tablename__ = 'greetings'

    name: Mapped[str] = mapped_column(String(255), primary_key=True)
    first_greeted: Mapped[datetime] = mapped_column(DateTime(True), insert_default=sa.func.now())


@app.route('/database/setup')
def database_setup():
    Base.metadata.create_all(bind=init_unix_connection_engine())
    return Response(status=200)


@app.route('/task/greeted', methods=['POST'])
def greeted_task():
    queue_name = request.headers.get('X-Appengine-Queuename')
    if queue_name is None or queue_name not in ALLOWED_QUEUES:
        return Response('Only Cloud Tasks can call this route', status=401)
    
    name = request.data.decode('utf-8')

    with Session(init_unix_connection_engine()) as cursor:
        greeting = Greeting(name=name)
        cursor.merge(greeting)
        cursor.commit()
        cursor.refresh(greeting)

    print(f'{name} first greeted on {greeting.first_greeted}')

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

def init_unix_connection_engine() -> sa.Engine:
    db_config = {
        "pool_size": 5,
        "max_overflow": 1,
        "pool_timeout": 30,
        "pool_recycle": 1800,
    }

    db_name = os.environ.get('DB_NAME')
    db_user = os.environ.get('DB_USER')
    db_pass = os.environ.get('DB_PASS')
    instance_connection_name = os.environ.get('INSTANCE_CONNECTION_NAME')

    engine = sa.create_engine(
        # Equivalent URL:
        # mysql+pymysql://<db_user>:<db_pass>@/<db_name>?unix_socket=<socket_path>/<cloud_sql_instance_name>
        sa.engine.url.URL.create(
            drivername="mysql+pymysql",
            username=db_user,
            password=db_pass,
            database=db_name,
            query={
                "unix_socket": f"/cloudsql/{instance_connection_name}"
            }
        ),
        **db_config
    )

    return engine
