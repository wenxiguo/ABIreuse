import streamlit as st
import pandas as pd
import tempfile
import requests
from PIL import Image
from fpdf import FPDF
from io import BytesIO
import os

st.set_page_config(page_title="重复图片组查看工具", layout="wide")
st.title("🖼️ 重复图片组查看工具")
st.write("上传包含 `照片地址`, `拜访id`, `相似组` 字段的 CSV/XLSX 文件")

# ─── 上传文件 ─────────────────────────────
uploaded_file = st.file_uploader("📄 上传文件", type=["csv", "xlsx"])
if uploaded_file is not None:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file, engine="openpyxl")

    df.columns = df.columns.str.strip()
    required_cols = {'照片地址', '拜访id', '相似组'}
    if not required_cols.issubset(df.columns):
        st.error("❌ 缺少必要列：照片地址 / 拜访id / 相似组")
        st.stop()

    df = df[df['相似组'].notna()]
    df['相似组'] = df['相似组'].astype(str)

    group_ids = sorted(df['相似组'].unique())
    if 'group_index' not in st.session_state:
        st.session_state.group_index = 0

    current_index = st.session_state.group_index
    group_id = group_ids[current_index]

    st.subheader(f"🔁 当前相似组：{group_id}　（{current_index + 1} / {len(group_ids)}）")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("⬅️ 上一组") and current_index > 0:
            st.session_state.group_index -= 1
            st.rerun()
    with col2:
        if st.button("➡️ 下一组") and current_index < len(group_ids) - 1:
            st.session_state.group_index += 1
            st.rerun()

    current_group_df = df[df['相似组'] == group_id].reset_index(drop=True)
    num_images = len(current_group_df)
    st.markdown(f"### 当前组共有 {num_images} 张图片")

    cols = st.columns(min(num_images, 6))
    for i in range(num_images):
        with cols[i % len(cols)]:
            img_url = current_group_df.at[i, '照片地址']
            st.image(img_url, use_column_width=True)
            info_lines = []
            for col in current_group_df.columns:
                if col not in ['照片地址', '相似组']:
                    info_lines.append(f"**{col}**: {current_group_df.at[i, col]}")
            st.markdown("<br>".join(info_lines), unsafe_allow_html=True)

    # ─── PDF导出区域 ─────────────────────────────
    st.markdown("---")
    st.markdown("### 🧾 导出 PDF")
    export_n = st.number_input("导出前 N 组相似组", min_value=1, max_value=len(group_ids), value=1, step=1)
    max_per_group = st.number_input("每组最多导出图片数量", min_value=1, value=5, step=1)
    if st.button("📤 导出 PDF"):

        with st.spinner("正在生成 PDF，请稍候..."):

            class PDF(FPDF):
                def __init__(self):
                    super().__init__()
                    self.set_auto_page_break(auto=True, margin=15)

                def header(self):
                    self.set_font("Arial", "B", 12)
                    self.cell(0, 10, f"重复图片组查看 - 第{self.page_no()}页", ln=True, align="C")

            pdf = PDF()
            pdf.set_font("Arial", size=10)

            for i in range(export_n):
                gid = group_ids[i]
                gdf = df[df['相似组'] == gid].reset_index(drop=True)
                pdf.add_page()
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, f"相似组：{gid}", ln=True)

                for j, row in gdf.iloc[:max_per_group].iterrows():
                    try:
                        response = requests.get(row['照片地址'], timeout=5)
                        img = Image.open(BytesIO(response.content)).convert("RGB")
                        temp_img_path = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                        img.save(temp_img_path)
                        pdf.image(temp_img_path, w=60)
                        os.unlink(temp_img_path)
                    except Exception as e:
                        pdf.set_font("Arial", size=10)
                        pdf.cell(0, 10, f"图片加载失败: {e}", ln=True)

                    for col in gdf.columns:
                        if col not in ['照片地址', '相似组']:
                            pdf.multi_cell(0, 8, f"{col}: {row[col]}")
                    pdf.ln(5)

            output_pdf_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            pdf.output(output_pdf_path)

        with open(output_pdf_path, "rb") as f:
            st.success("✅ PDF 已生成！请点击下方按钮下载：")
            st.download_button(
                label="📥 下载 PDF 文件",
                data=f,
                file_name="重复图片组.pdf",
                mime="application/pdf"
            )

else:
    st.info("请上传一个有效的 CSV/XLSX 文件。")
