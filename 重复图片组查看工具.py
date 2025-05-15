import streamlit as st
import pandas as pd
import tempfile
import requests
from PIL import Image
from fpdf import FPDF
from io import BytesIO
import os

# ─── 查系统 TTF 字体 + 远程下载备选 ───────────────────────────────────────
def get_chinese_font():
    # 1) 本地扫描 TrueType 文件
    search_dirs = [
        '/usr/share/fonts', '/usr/local/share/fonts',
        '/System/Library/Fonts', '/Library/Fonts'
    ]
    for base in search_dirs:
        if os.path.isdir(base):
            for root, _, files in os.walk(base):
                for fn in files:
                    if fn.lower().endswith('.ttf') and \
                       any(k in fn.lower() for k in ('noto','wqy','hei','song','fang')):
                        return os.path.join(root, fn)

    # 2) 远程下载 variable TTF：NotoSansSC[wght].ttf
    remote = "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf"
    tmp = os.path.join(tempfile.gettempdir(), "NotoSansSC[wght].ttf")
    if not os.path.exists(tmp):
        resp = requests.get(remote, timeout=20)
        resp.raise_for_status()
        with open(tmp, "wb") as f:
            f.write(resp.content)
    return tmp

# ─── 自定义横向 A4 PDF ───────────────────────────────────────────────────────
class PDF(FPDF):
    def __init__(self, font_path: str):
        super().__init__(orientation='L', format='A4')
        self.set_auto_page_break(auto=False)
        self.add_font('ChFont', '', font_path, uni=True)

# ─── Streamlit 应用 ───────────────────────────────────────────────────────────
st.set_page_config(page_title="重复图片组查看工具", layout="wide")
st.title("🖼️ 重复图片组查看工具")
st.write("上传包含 `照片地址`、`相似组` 以及其他字段的 CSV/XLSX 文件")

# 上传 & 读取
uploaded = st.file_uploader("📄 上传 CSV / XLSX", type=["csv","xlsx"])
if not uploaded:
    st.info("请先上传文件。")
    st.stop()

if uploaded.name.lower().endswith(".csv"):
    df = pd.read_csv(uploaded)
else:
    df = pd.read_excel(uploaded, engine="openpyxl")
df.columns = df.columns.str.strip()

# 校验必选列
if not {'照片地址','相似组'}.issubset(df.columns):
    st.error("缺少必要列：照片地址 / 相似组")
    st.stop()

df = df[df['相似组'].notna()].copy()
df['相似组'] = df['相似组'].astype(str)

# 字段多选
fields = [c for c in df.columns if c not in ['照片地址','相似组']]
selected = st.multiselect("✅ 选择要在 PDF 中展示的字段", options=fields, default=fields)

# 分组导航
group_ids = sorted(df['相似组'].unique())
st.session_state.setdefault('group_index', 0)
idx = st.session_state.group_index
gid = group_ids[idx]
st.subheader(f"🔁 当前相似组：{gid} （{idx+1}/{len(group_ids)}）")
c1, c2 = st.columns(2)
with c1:
    if st.button("⬅️ 上一组") and idx > 0:
        st.session_state.group_index -= 1
        st.rerun()
with c2:
    if st.button("➡️ 下一组") and idx < len(group_ids) - 1:
        st.session_state.group_index += 1
        st.rerun()

# 预览
grp = df[df['相似组'] == gid].reset_index(drop=True)
st.markdown(f"### 当前组共有 {len(grp)} 张图片")
preview_cols = st.columns(min(len(grp), 6))
for i, row in grp.iterrows():
    with preview_cols[i % len(preview_cols)]:
        st.image(row['照片地址'], use_container_width=True)
        info = [f"**{f}**: {row[f]}" for f in selected]
        st.markdown("<br>".join(info), unsafe_allow_html=True)

# 导出设置
st.markdown("---")
st.markdown("### 🧾 导出 PDF （横向 A4，每页一组）")
export_n = st.number_input("导出前 N 组", min_value=1, max_value=len(group_ids), value=1)
max_per = st.number_input("每组最多导出图片数", min_value=1, value=5)

if st.button("📤 生成并下载 PDF"):
    # 获取或下载字体
    try:
        font_path = get_chinese_font()
    except Exception as e:
        st.error(f"❌ 无法获取中文字体：{e}")
        st.stop()

    with st.spinner("生成 PDF 中，请稍候..."):
        pdf = PDF(font_path)
        pdf.set_margins(15, 15, 15)
        page_w = pdf.w - pdf.l_margin - pdf.r_margin
        page_h = pdf.h - pdf.t_margin - pdf.b_margin

        for gi in range(export_n):
            sub = df[df['相似组'] == group_ids[gi]].reset_index(drop=True)
            n = min(len(sub), max_per)
            if n == 0:
                continue

            pdf.add_page()
            pdf.set_font('ChFont', '', 14)
            pdf.cell(0, 10, f"相似组：{group_ids[gi]}", ln=True)
            y0 = pdf.get_y() + 2

            spacing = 5
            cell_w = (page_w - spacing * (n - 1)) / n
            reserved_h = (page_h - (y0 - pdf.t_margin)) * 0.25
            img_h_max = page_h - (y0 - pdf.t_margin) - reserved_h

            for i in range(n):
                row = sub.iloc[i]
                try:
                    resp = requests.get(row['照片地址'], timeout=5)
                    img = Image.open(BytesIO(resp.content))
                    ow, oh = img.size
                    h_img = min(oh / ow * cell_w, img_h_max)

                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                    img.convert("RGB").save(tmp)

                    x = pdf.l_margin + i * (cell_w + spacing)
                    pdf.image(tmp, x=x, y=y0, w=cell_w, h=h_img)
                    os.unlink(tmp)

                    pdf.set_xy(x, y0 + h_img + 2)
                    pdf.set_font('ChFont', '', 8)
                    txt = "\n".join(f"{f}: {row[f]}" for f in selected)
                    pdf.multi_cell(cell_w, 4, txt)
                except Exception:
                    continue

        out_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
        pdf.output(out_path)

    with open(out_path, "rb") as f:
        st.success("✅ PDF 已生成！")
        st.download_button("📥 下载 PDF", data=f, file_name="重复图片组.pdf", mime="application/pdf")
