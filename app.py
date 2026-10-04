import streamlit as st
import pandas as pd
import subprocess
import json
import tempfile
from pathlib import Path

# ========== 首次启动时用 R 装缺失的 CRAN 包 ==========
_R_PKGS = ["randomForest", "xgboost", "cluster"]
_R_INSTALL = f'''
pkgs <- c({", ".join(f'"{p}"' for p in _R_PKGS)})
missing <- pkgs[!sapply(pkgs, requireNamespace, quietly = TRUE)]
if (length(missing) > 0) {{
  install.packages(missing, repos = "https://cloud.r-project.org")
}}
'''
try:
    subprocess.run(["Rscript", "-e", _R_INSTALL], check=False, timeout=1800)
except Exception as e:
    print(f"R 包安装失败: {e}")

# ========== 页面 ==========
st.set_page_config(page_title="鸭芯智选", layout="wide")
st.title("🦆 鸭芯智选 V5.0")


def call_r(script, config):
    with tempfile.TemporaryDirectory() as tmp:
        inp = Path(tmp) / "in.json"
        out = Path(tmp) / "out.json"
        config["output"] = str(out)
        inp.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            ["Rscript", script, str(inp), str(out)],
            capture_output=True, text=True, timeout=1800
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr)
        return json.loads(out.read_text(encoding="utf-8"))


st.sidebar.header("上传数据")
feed_files = st.sidebar.file_uploader("采食表", type=["xls", "xlsx"], accept_multiple_files=True)
bw_files = st.sidebar.file_uploader("体重表", type=["xls", "xlsx"], accept_multiple_files=True)
ped_file = st.sidebar.file_uploader("系谱（可选）", type=["xls", "xlsx"])

st.sidebar.header("育种目标")
goals = st.sidebar.multiselect(
    "选择目标", ["save", "grow", "fat", "meat", "rhythm"],
    default=["save", "grow"],
    format_func=lambda x: {"save": "吃得省", "grow": "长得快", "fat": "皮脂厚",
                            "meat": "胸肌厚", "rhythm": "采食规律"}[x]
)

ratio = st.sidebar.slider("留种比例 (%)", 5, 80, 30)
sex_balance = st.sidebar.checkbox("公母均衡", value=True)

if st.sidebar.button("开始计算", type="primary"):
    if not feed_files or not bw_files:
        st.error("请上传采食表和体重表")
        st.stop()

    tmpdir = Path(tempfile.mkdtemp())
    feed_paths = []
    for f in feed_files:
        p = tmpdir / f.name
        p.write_bytes(f.read())
        feed_paths.append(str(p))
    bw_paths = []
    for f in bw_files:
        p = tmpdir / f.name
        p.write_bytes(f.read())
        bw_paths.append(str(p))
    ped_path = None
    if ped_file:
        p = tmpdir / ped_file.name
        p.write_bytes(ped_file.read())
        ped_path = str(p)

    with st.spinner("R 引擎计算中..."):
        try:
            result = call_r("r/duck_tool_V5_simple.R", {
                "feed_files": feed_paths,
                "bw_files": bw_paths,
                "ped_path": ped_path,
                "goals": goals,
                "ratio": ratio,
                "sex_balance": sex_balance
            })
            st.success("计算完成")
            st.dataframe(pd.DataFrame(result.get("summary", [])))
            st.dataframe(pd.DataFrame(result.get("retained", [])))
        except Exception as e:
            st.error(f"失败：{e}")
