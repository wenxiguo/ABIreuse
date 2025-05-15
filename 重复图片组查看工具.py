import streamlit as st
import pandas as pd
import tempfile
import requests
from PIL import Image
from fpdf import FPDF
from io import BytesIO
import os
import math

# ─── 自动查找中文字体 ──────────────────────────────────────────────────────
def find_chinese_font():
    # 常见安装路径列表
    candidates = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto-cjk/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/usr/share/fonts/truetype/arphic/uming.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
        '/Library/Fonts/PingFang.ttc',
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

# ─── 自定义 PDF 类 ─────────────────────────────────────────────────────────
class PDF(FPDF):
    def __init__(self, font_path: str):
        super().__init__(orientation='L', format='A4')
        self.set_auto_page_break(auto=False)
        # 注册字体
        self.add_font('ChFont', '', font_path, uni=True)

# ─── Streamlit APP ─────────────────────────────────────────────────────────
st.set_page_config(page_title="重复图片组查看工具", layout="wide")
st.title("🖼️ 重复图片组查看工具")
st.write("上传包含 `照片地址`, `相似组` 以及任意自定义字段的 CSV/XLSX 文件")

# 上传文件
uploaded_file = st.file_uploader("📄 上传文件", type=["csv", "xlsx"])
if not uploaded_file:
    st.info("请上传一个有效的 CSV 或 XLSX 文件。")
    st.stop()

# 读取数据
if uploaded_file.name.lower().endswith(".csv"):
    df = pd.read_csv(uploaded_file)
else:
    df = pd.read_excel(uploaded_file, engine="openpyxl")
df.columns = df.columns.str.strip()

# 校验必须列
required = {'照片地址', '相似组'}
if not required.issubset(df.columns):
    st.error("❌ 缺少必要列：照片地址 / 相似组")
    st.stop()

# 过滤空组并转字符串
df = df[df['相似组'].notna()].copy()
df['相似组'] = df['相似组'].astype(str)

# 字段选择
all_fields = [c for c in df.columns if c not in ['照片地址','相似组']]
selected_fields = st.multiselect(
    "✅ 选择要在 PDF 中展示的字段",
    options=all_fields,
    default=all_fields
)

# 分组导航
group_ids = sorted(df['相似组'].unique())
st.session_state.setdefault('group_index', 0)
idx = st.session_state.group_index
gid = group_ids[idx]

st.subheader(f"🔁 当前相似组：{gid}　（{idx+1}/{len(group_ids)}）")
c1, c2 = st.columns(2)
with c1:
    if st.button("⬅️ 上一组") and idx > 0:
        st.session_state.group_index -= 1
        st.rerun()
with c2:
    if st.button("➡️ 下一组") and idx < len(group_ids)-1:
        st.session_state.group_index += 1
        st.rerun()

# 预览当前组
grp = df[df['相似组'] == gid].reset_index(drop=True)
st.markdown(f"### 当前组共有 {len(grp)} 张图片")
preview_cols = st.columns(min(len(grp), 6))
for i, row in grp.iterrows():
    with preview_cols[i % len(preview_cols)]:
        st.image(row['照片地址'], use_column_width=True)
        info = [f"**{f}**: {row[f]}" for f in selected_fields]
        st.markdown("<br>".join(info), unsafe_allow_html=True)

# 导出设置
st.markdown("---")
st.markdown("### 🧾 导出 PDF （横向 A4，每页一组）")
export_n = st.number_input("导出前 N 组", min_value=1, max_value=len(group_ids), value=1)
max_per = st.number_input("每组最多导出图片数", min_value=1, value=5)

if st.button("📤 生成并下载 PDF"):
    # 查字体
    font_path = find_chinese_font()
    if not font_path:
        st.error("❌ 未找到中文字体，请在 apt.txt 安装 `fonts-noto-cjk` 或 `fonts-wqy-zenhei`。")
        st.stop()

    with st.spinner("正在生成 PDF，请稍候..."):
        pdf = PDF(font_path)
        pdf.set_margins(15, 15, 15)
        page_w = pdf.w - pdf.l_margin - pdf.r_margin
        page_h = pdf.h - pdf.t_margin - pdf.b_margin

        for gi in range(export_n):
            sub_df = df[df['相似组'] == group_ids[gi]].reset_index(drop=True)
            n = min(len(sub_df), max_per)
            if n == 0:
                continue

            pdf.add_page()
            # 组标题
            pdf.set_font('ChFont', '', 14)
            pdf.cell(0, 10, f"相似组：{group_ids[gi]}", ln=True)
            y0 = pdf.get_y() + 2

            # 计算每张图可用宽度与高度
            spacing = 5
            cell_w = (page_w - spacing*(n-1)) / n
            # 留出 25% 用于文字
            reserved_h = (page_h - (y0 - pdf.t_margin)) * 0.25
            img_h_max = page_h - (y0 - pdf.t_margin) - reserved_h

            for i in range(n):
                row = sub_df.iloc[i]
                try:
                    resp = requests.get(row['照片地址'], timeout=5)
                    img = Image.open(BytesIO(resp.content))
                    ow, oh = img.size
                    h_img = min(oh/ow * cell_w, img_h_max)

                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
                    img.convert("RGB").save(tmp)

                    x = pdf.l_margin + i*(cell_w + spacing)
                    pdf.image(tmp, x=x, y=y0, w=cell_w, h=h_img)
                    os.unlink(tmp)

                    # 文本区
                    pdf.set_xy(x, y0 + h_img + 2)
                    pdf.set_font('ChFont', '', 8)
                    text = "\n".join(f"{f}: {row[f]}" for f in selected_fields)
                    pdf.multi_cell(cell_w, 4, text)
                except Exception:
                    continue

        # 输出临时文件并下载
        out_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
        pdf.output(out_path)

    with open(out_path, "rb") as f:
        st.success("✅ PDF 已生成！")
        st.download_button(
            label="📥 下载 PDF",
            data=f,
            file_name="重复图片组.pdf",
            mime="application/pdf"
        )
