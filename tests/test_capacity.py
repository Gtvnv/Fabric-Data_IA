import pytest
from infra.capacity import CapacityError, main, run


class FakeClient:
    def __init__(self):
        self.calls = []

    def suspend(self, capacity_id):
        self.calls.append(("suspend", capacity_id))

    def resume(self, capacity_id):
        self.calls.append(("resume", capacity_id))


@pytest.mark.parametrize("env", ["dev", "test"])
def test_pause_and_resume_non_prod(env):
    c = FakeClient()
    run("pause", env, "/cap/1", c)
    run("resume", env, "/cap/1", c)
    assert c.calls == [("suspend", "/cap/1"), ("resume", "/cap/1")]


@pytest.mark.parametrize("action", ["pause", "resume"])
def test_prod_refused(action):
    c = FakeClient()
    with pytest.raises(CapacityError):
        run(action, "prod", "/cap/1", c)
    assert c.calls == []


def test_invalid_env_and_action():
    c = FakeClient()
    with pytest.raises(CapacityError):
        run("pause", "qa", "/cap/1", c)
    with pytest.raises(CapacityError):
        run("delete", "dev", "/cap/1", c)
    assert c.calls == []


def test_cli_exit_codes():
    c = FakeClient()
    assert main(["pause", "--env", "dev", "--capacity-id", "/cap/1"], client=c) == 0
    assert main(["pause", "--env", "prod", "--capacity-id", "/cap/1"], client=c) == 2
    assert c.calls == [("suspend", "/cap/1")]
