import os, sqlite3, subprocess, sys
from pathlib import Path
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from app.models import Feedback, FeedbackCandidate, FeedbackCandidateRequirement

BACKEND=Path(__file__).resolve().parents[1]
TABLES={"feedback","feedback_candidates","feedback_candidate_requirements"}
def alembic(path,*args):
    env={**os.environ,"DATABASE_URL":f"sqlite:///{path}","PYTHONPATH":str(BACKEND)+os.pathsep+os.environ.get("PYTHONPATH","")}
    subprocess.run([sys.executable,"-m","alembic",*args],cwd=BACKEND,env=env,check=True,capture_output=True,text=True)
def tables(path):
    with sqlite3.connect(path) as c: return {r[0] for r in c.execute("select name from sqlite_master where type='table'")}
def test_feedback_migration_upgrade_and_downgrade(tmp_path):
    p=tmp_path/"f.db"; alembic(p,"upgrade","head"); assert TABLES <= tables(p)
    alembic(p,"downgrade","0007"); assert not TABLES & tables(p)
    alembic(p,"upgrade","head"); assert TABLES <= tables(p)
def test_feedback_models_compile_for_postgresql():
    for model in (Feedback,FeedbackCandidate,FeedbackCandidateRequirement):
        ddl=str(CreateTable(model.__table__).compile(dialect=postgresql.dialect()))
        assert "CREATE TYPE" not in ddl
