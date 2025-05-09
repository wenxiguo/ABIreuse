import streamlit as st
import pandas as pd

st.set_page_config(page_title="重复图片组查看工具", layout="wide")
st.title("🖼️ 重复图片组查看工具")
st.write("上传包含 `图片`, `pocid`, `重复组` 字段的 CSV 文件")

# ─── 上传 CSV ─────────────────────────────────────
uploaded_file = st.file_uploader("📄 上传文件（支持 CSV / XLSX）", type=["csv", "xlsx"])
if uploaded_file is not None:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    elif uploaded_file.name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file, engine="openpyxl")
    df.columns = df.columns.str.strip()
    if not {'图片', 'pocid', '重复组'}.issubset(df.columns):
        st.error("❌ 缺少必要列：图片 / pocid / 重复组")
        st.stop()

    # 只保留重复组非空的记录
    df = df[df['重复组'].notna()]
    df['重复组'] = df['重复组'].astype(str)

    # 获取所有重复组编号
    group_ids = sorted(df['重复组'].unique())
    if 'group_index' not in st.session_state:
        st.session_state.group_index = 0

    current_index = st.session_state.group_index
    group_id = group_ids[current_index]

    # ─── 展示当前组编号（主页面） ─────────────────────────
    st.subheader(f"🔁 当前重复组：{group_id}　（{current_index + 1} / {len(group_ids)}）")

    # ─── 切换按钮（主页面） ───────────────────────────────
    col_nav1, col_nav2 = st.columns([1, 1])
    with col_nav1:
        if st.button("⬅️ 上一组") and current_index > 0:
            st.session_state.group_index -= 1
            st.rerun()
    with col_nav2:
        if st.button("➡️ 下一组") and current_index < len(group_ids) - 1:
            st.session_state.group_index += 1
            st.rerun()

    # ─── 展示当前组内的图片 ──────────────────────────────
    current_group_df = df[df['重复组'] == group_id].reset_index(drop=True)
    num_images = len(current_group_df)

    st.markdown(f"### 当前组共有 {num_images} 张图片")
    cols = st.columns(num_images)
    for i in range(num_images):
        with cols[i]:
            img_url = current_group_df.at[i, '图片']
            st.image(img_url, use_container_width=True)
            info_lines = []
            for col in current_group_df.columns:
                if col not in ['图片', '重复组']:
                    value = current_group_df.at[i, col]
                    info_lines.append(f"**{col}**: {value}")
            st.markdown("<br>".join(info_lines), unsafe_allow_html=True)

else:
    st.info("请上传一个有效的 CSV 文件")
