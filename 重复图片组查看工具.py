import streamlit as st
import pandas as pd
import tempfile
import requests
from PIL import Image
from fpdf import FPDF
from io import BytesIO
import os
import math

st.set_page_config(page_title="重复图片组查看工具", layout="wide")
st.title("🖼️ 重复图片组查看工具")
st.write("上传包含 `照片地址`, `拜访id`, `相似组` 字段的 CSV/XLSX 文件")

# ─── 上传文件 ────────────────────────────────────
uploaded_file = st.file_uploader("📄 上传文件", type=["csv", "xlsx"])
if not uploaded_file:
    st.info("请上传一个有效的 CSV/XLSX 文件。")
    st.stop()

# 读取与预处理
if uploaded_file.name.lower().endswith(".csv"):
    df = pd.read_csv(uploaded_file)
else:
    df = pd.read_excel(uploaded_file, engine="openpyxl")
df.columns = df.columns.str.strip()
required = {'照片地址', '相似组'}
if not required.issubset(df.columns):
    st.error("❌ 缺少必要列：照片地址 / 相似组")
    st.stop()
df = df[df['相似组'].notna()].copy()
df['相似组'] = df['相似组'].astype(str)

# 字段选择
all_fields = [c for c in df.columns if c not in ['照片地址','相似组']]
selected = st.multiselect("选择 PDF 中要展示的字段", options=all_fields, default=all_fields)

# 分组导航
group_ids = sorted(df['相似组'].unique())
st.session_state.setdefault('group_index', 0)
idx = st.session_state.group_index
gid = group_ids[idx]
st.subheader(f"🔁 当前相似组：{gid}　（{idx+1}/{len(group_ids)}）")
c1, c2 = st.columns(2)
with c1:
    if st.button("⬅️ 上一组") and idx>0:
        st.session_state.group_index -= 1; st.rerun()
with c2:
    if st.button("➡️ 下一组") and idx< len(group_ids)-1:
        st.session_state.group_index += 1; st.rerun()

# 预览
grp = df[df['相似组']==gid].reset_index(drop=True)
st.markdown(f"### 当前组共有 {len(grp)} 张图片")
cols = st.columns(min(len(grp), 6))
for i, row in grp.iterrows():
    with cols[i % len(cols)]:
        st.image(row['照片地址'], use_column_width=True)
        info = [f"**{f}**: {row[f]}" for f in selected]
        st.markdown("<br>".join(info), unsafe_allow_html=True)

# 导出设置
st.markdown("---")
st.markdown("### 🧾 导出 PDF （横向 A4，每页一组）")
export_n = st.number_input("导出前 N 组", min_value=1, max_value=len(group_ids), value=1)
max_per = st.number_input("每组最多导出图片数", min_value=1, value=5)

if st.button("📤 导出 PDF"):
    with st.spinner("正在生成 PDF，请稍候..."):

        class PDF(FPDF):
            def __init__(self):
                super().__init__(orientation='L', format='A4')
                self.set_auto_page_break(auto=False)
                self.add_font('SimHei', '', 'SimHei.ttf', uni=True)

        pdf = PDF()
        m = 15
        pdf.set_margins(m, m, m)
        page_w = pdf.w - 2*m
        page_h = pdf.h - m - pdf.b_margin

        for gi in range(export_n):
            sub = df[df['相似组']==group_ids[gi]].reset_index(drop=True)
            n = min(len(sub), max_per)
            if n == 0: continue

            pdf.add_page()
            # 组标题
            pdf.set_font('SimHei','',14)
            pdf.cell(0,10, f"相似组：{group_ids[gi]}", ln=True)
            y0 = pdf.get_y() + 2

            # 布局
            spacing = 5
            cell_w = (page_w - spacing*(n-1)) / n
            # 为文字预留 25% 的高度
            reserved_text_h = (page_h - (y0 - m)) * 0.25
            available_img_h = page_h - (y0 - m) - reserved_text_h

            for i in range(n):
                row = sub.iloc[i]
                try:
                    resp = requests.get(row['照片地址'], timeout=5)
                    img = Image.open(BytesIO(resp.content))
                    ow, oh = img.size
                    # 限制图片高度
                    h_img = min(oh/ow * cell_w, available_img_h)
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                    img.convert("RGB").save(tmp)

                    x = m + i*(cell_w+spacing)
                    pdf.image(tmp, x=x, y=y0, w=cell_w, h=h_img)
                    os.unlink(tmp)

                    # 打印元数据在图片下方
                    pdf.set_xy(x, y0 + h_img + 2)
                    pdf.set_font('SimHei','',8)
                    info = "\n".join(f"{f}: {row[f]}" for f in selected)
                    pdf.multi_cell(cell_w, 4, info)
                except Exception:
                    continue

        out = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
        pdf.output(out)

    with open(out, "rb") as f:
        st.success("✅ PDF 已生成！点击下载：")
        st.download_button("📥 下载 PDF", f, file_name="重复图片组.pdf", mime="application/pdf")
