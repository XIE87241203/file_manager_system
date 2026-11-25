import json
import os
import subprocess
import sys
from typing import List

import quickjs

# 默认文件名整理脚本文件名（系统首次运行时生成到 data 目录）
DEFAULT_SCRIPT_FILENAME: str = 'default.js'
# 校验脚本时使用的样例文件名（含后缀）
_SAMPLE_FILE_NAME: str = 'sample.mp4'
# 保存设置时校验脚本的超时秒数（防死循环）
_VALIDATE_TIMEOUT_SECONDS: int = 5
# 沙箱内存上限（64MB），防止脚本恶意申请内存
_SANDBOX_MEMORY_LIMIT: int = 64 * 1024 * 1024

# 首次运行生成的默认脚本模板：rename 原样返回入参，即不做任何改名
_DEFAULT_SCRIPT_CONTENT: str = '''// 默认文件名整理脚本（系统首次运行时自动生成）
// 约定：脚本必须提供 rename 方法。
//   入参：fileName - 原始文件名字符串（包括后缀），例如 "My Video.mp4"
//   出参：整理完成的文件名字符串（包括后缀），例如 "my_video.mp4"
// 设置中“文件名整理脚本”路径留空时，使用本默认脚本（原样返回文件名，不改名）。
// 自定义方法：复制本文件并修改 rename 实现，再把新文件路径填入“整理设置 → 文件名整理脚本”。
function rename(fileName) {
    return fileName;
}
'''


def get_default_script_path() -> str:
    """
    用途说明：获取默认文件名整理脚本的绝对路径（data/default.js）。
    入参说明：无。
    返回值说明：str - 默认脚本绝对路径。
    """
    from backend.common.utils import Utils
    return os.path.join(Utils.get_runtime_path(), DEFAULT_SCRIPT_FILENAME)


def ensure_default_script() -> None:
    """
    用途说明：系统首次运行时生成默认整理脚本 default.js；文件已存在时不做任何覆盖。
    入参说明：无。
    返回值说明：无。
    """
    from backend.common.i18n_utils import t
    from backend.common.log_utils import LogUtils
    path: str = get_default_script_path()
    if os.path.exists(path):
        return
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(_DEFAULT_SCRIPT_CONTENT)
        LogUtils.info(t('organize_default_script_created', path=path))
    except Exception as e:
        LogUtils.error(t('organize_script_read_error', error=str(e)))


def resolve_script_path(script_path: str) -> str:
    """
    用途说明：解析实际生效的整理脚本路径；设置留空时回退到默认脚本 default.js。
    入参说明：script_path (str) - 设置中配置的脚本路径，允许为空。
    返回值说明：str - 实际生效的脚本绝对/相对路径。
    """
    path: str = (script_path or '').strip()
    return path if path else get_default_script_path()


def validate_rename_script(script_path: str) -> None:
    """
    用途说明：保存整理设置前校验用户脚本：须为 .js 文件、文件存在、提供 rename 方法且对样例文件名返回合法字符串。
    入参说明：script_path (str) - 设置中配置的脚本路径，空字符串表示使用默认脚本，直接通过。
    返回值说明：无。
    异常说明：ValueError - 校验失败时抛出（携带多语言文案），由路由层转换为 400 响应。
    """
    from backend.common.i18n_utils import t
    path: str = (script_path or '').strip()
    if not path:
        return
    if not path.lower().endswith('.js'):
        raise ValueError(t('organize_script_not_js', path=path))
    if not os.path.isfile(path):
        raise ValueError(t('organize_script_not_found', path=path))
    result: dict = _run_worker(path, [_SAMPLE_FILE_NAME], _VALIDATE_TIMEOUT_SECONDS)
    if not result.get('ok'):
        _raise_for_worker_error(result)


def rename_file_names(script_path: str, names: List[str]) -> List[str]:
    """
    用途说明：整理流程批量改名入口：在沙箱子进程中执行脚本 rename 方法，逐个返回整理后的文件名。
    入参说明：
        script_path (str) - 设置中配置的脚本路径，空字符串时使用默认脚本 default.js。
        names (List[str]) - 原始文件名列表（包括后缀）。
    返回值说明：List[str] - 与入参一一对应的整理后文件名列表。
    异常说明：ValueError - 脚本不存在/执行失败/返回非法/超时时抛出（携带多语言文案）。
    """
    if not names:
        return []
    path: str = resolve_script_path(script_path)
    timeout: float = 10 + len(names) * 0.05
    result: dict = _run_worker(path, names, timeout)
    if not result.get('ok'):
        _raise_for_worker_error(result)
    return result.get('results', [])


def _run_worker(script_path: str, names: List[str], timeout: float) -> dict:
    """
    用途说明：启动沙箱子进程执行脚本（quickjs 无系统访问能力），父进程超时强杀，防止死循环拖垮服务。
    入参说明：
        script_path (str) - 待执行的脚本路径。
        names (List[str]) - 交给 rename 处理的文件名列表（JSON 经 stdin 传入）。
        timeout (float) - 子进程超时秒数。
    返回值说明：dict - 子进程 stdout 的 JSON 结果 {ok, results} 或 {ok: False, code, detail}。
    异常说明：ValueError - 超时或子进程输出无法解析时抛出。
    """
    from backend.common.i18n_utils import t
    root: str = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    env: dict = os.environ.copy()
    env['PYTHONPATH'] = root + os.pathsep + env.get('PYTHONPATH', '')
    cmd: List[str] = [sys.executable, '-m', 'backend.organize.rename_script', '--worker', script_path]
    kwargs: dict = {}
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    try:
        proc = subprocess.run(
            cmd, input=json.dumps(names, ensure_ascii=False),
            capture_output=True, text=True, encoding='utf-8',
            timeout=timeout, env=env, cwd=root, **kwargs
        )
    except subprocess.TimeoutExpired:
        raise ValueError(t('organize_script_timeout'))
    try:
        return json.loads(proc.stdout)
    except Exception:
        detail: str = (proc.stderr or proc.stdout or '').strip()[-500:]
        raise ValueError(t('organize_script_exec_error', error=detail))


def _raise_for_worker_error(result: dict) -> None:
    """
    用途说明：把子进程返回的错误码翻译为多语言 ValueError 抛出。
    入参说明：result (dict) - 子进程错误结果 {ok: False, code, detail}。
    返回值说明：无（必然抛出异常）。
    异常说明：ValueError - 对应错误码的多语言文案。
    """
    from backend.common.i18n_utils import t
    code: str = result.get('code', '')
    detail: str = result.get('detail', '')
    if code == 'not_found':
        raise ValueError(t('organize_script_not_found', path=detail))
    if code == 'read_error':
        raise ValueError(t('organize_script_read_error', error=detail))
    if code == 'missing_rename':
        raise ValueError(t('organize_script_missing_rename'))
    if code == 'bad_return':
        raise ValueError(t('organize_script_bad_return'))
    if code == 'invalid_name':
        raise ValueError(t('organize_script_invalid_name'))
    raise ValueError(t('organize_script_exec_error', error=detail))


def _worker_main(script_path: str) -> None:
    """
    用途说明：子进程入口：读取 stdin 的文件名列表，在 quickjs 沙箱中执行脚本 rename 并输出 JSON 结果。
    入参说明：script_path (str) - 待执行的脚本路径（命令行传入）。
    返回值说明：无（结果经 stdout 输出：{ok: True, results} 或 {ok: False, code, detail}）。
    """
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stdin.reconfigure(encoding='utf-8')
    names: List[str] = json.loads(sys.stdin.read())
    out: dict = {'ok': False, 'code': 'exec_error', 'detail': ''}
    try:
        if not os.path.isfile(script_path):
            out = {'ok': False, 'code': 'not_found', 'detail': script_path}
        else:
            with open(script_path, 'r', encoding='utf-8', errors='replace') as f:
                source: str = f.read()
            ctx = quickjs.Context()
            if hasattr(ctx, 'set_memory_limit'):
                ctx.set_memory_limit(_SANDBOX_MEMORY_LIMIT)
            if hasattr(ctx, 'set_max_stack_size'):
                ctx.set_max_stack_size(1024 * 1024)
            ctx.eval(source)
            # 在同一全局作用域内取 rename（兼容 function/var/let/const 等声明方式）
            fn = ctx.eval('typeof rename === "function" ? rename : undefined')
            if not callable(fn):
                out = {'ok': False, 'code': 'missing_rename', 'detail': ''}
            else:
                results: List[str] = []
                for name in names:
                    renamed = fn(name)
                    if not isinstance(renamed, str):
                        out = {'ok': False, 'code': 'bad_return', 'detail': ''}
                        break
                    if not renamed or '/' in renamed or '\\' in renamed:
                        out = {'ok': False, 'code': 'invalid_name', 'detail': ''}
                        break
                    results.append(renamed)
                else:
                    out = {'ok': True, 'results': results}
    except Exception as e:
        out = {'ok': False, 'code': 'exec_error', 'detail': str(e)}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '--worker':
        _worker_main(sys.argv[2])