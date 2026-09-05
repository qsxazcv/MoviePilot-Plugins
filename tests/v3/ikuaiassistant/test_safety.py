"""安全策略、预览与执行入口的离线回归测试。"""
import importlib.util
import sys
import shlex
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / 'plugins.v3' / 'ikuaiassistant'


def load_safety():
    """独立加载纯策略模块，不初始化宿主或联网。"""
    spec = importlib.util.spec_from_file_location('ikuai_safety_test', DIR / 'safety.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


S = load_safety()


@pytest.mark.parametrize('command', [
    'monitor system', 'monitor interfaces',
    'monitor clients-online --page-size 200', 'network dns get',
    'log system list --human-time --page-size 20 --order desc --order-by id',
    'routing stream five-tuple list --page-size 50',
    'routing stream load-balance list --page-size 50',
    'monitor traffic-load --ip 192.0.2.1 --mac aa:bb:cc:dd:ee:ff',
    'monitor client-protocols --ip 192.0.2.1 --mac aa:bb:cc:dd:ee:ff',
])
def test_read_commands(command):
    """覆盖八个斜杠入口依赖的固定和动态查询命令。"""
    assert S.check_command(shlex.split(command)) == {'ok': True, 'write': False}


@pytest.mark.parametrize('command', [
    'system restart', 'auth clear', 'unknown list',
    'monitor system --token fake', 'monitor system --bad x',
    'monitor clients-online --page-size 501',
    'routing stream five-tuple toggle 15',
    'routing stream five-tuple toggle 15 --enabled maybe',
    'routing stream five-tuple toggle 15 --enabled no --enabled yes',
])
def test_rejected_commands(command):
    """未知路径、越界和危险覆盖参数一律拒绝。"""
    assert not S.check_command(shlex.split(command))['ok']


def test_write_preview():
    """写入正确分类且预览只能成功消费一次。"""
    args = shlex.split('routing stream five-tuple toggle 15 --enabled no')
    assert S.check_command(args)['write']
    store = S.PreviewStore()
    key = store.create(args)
    assert store.consume(key, args)[0]
    assert not store.consume(key, args)[0]


def test_expiry_and_mismatch(monkeypatch):
    """模拟时间推进并拒绝篡改目标。"""
    monkeypatch.setattr(S.time, 'monotonic', lambda: 100)
    store = S.PreviewStore()
    key = store.create(['original'])
    assert not store.consume(key, ['changed'])[0]
    key = store.create(['original'])
    monkeypatch.setattr(S.time, 'monotonic', lambda: 401)
    assert not store.consume(key, ['original'])[0]


def test_concurrent_consume_and_isolation():
    """并发消费仅成功一次且不同实例不能共享预览。"""
    store = S.PreviewStore()
    key = store.create(['sample'])
    assert not S.PreviewStore().consume(key, ['sample'])[0]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.consume(key, ['sample'])[0], range(20)))
    assert sum(results) == 1


def test_capacity():
    """预览缓存有界。"""
    store = S.PreviewStore()
    for _ in range(300):
        store.create(['sample'])
    assert len(store._items) == 256
