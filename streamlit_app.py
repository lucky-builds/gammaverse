import shutil
import tempfile
from pathlib import Path

import streamlit as st

import export_iimjobs_applied as iimjobs_exporter
import remove_gamma_logo as pptx_cleaner
import remove_gamma_logo_pdf as pdf_cleaner

BASE_DIR = Path(__file__).resolve().parent
TOOL_WATERMARK = "Watermark remover"
TOOL_IIMJOBS = "iimjobs applied jobs export"
IIMJOBS_DEFAULT_OUTPUT = "iimjobs_applied_jobs.csv"


def process_pptx(src: Path, dest: Path) -> int:
    shutil.copy(src, dest)
    infos, contents = pptx_cleaner.load_archive(dest)
    layout_names = [
        name
        for name in contents
        if name.startswith("ppt/slideLayouts/") and name.endswith(".xml")
    ]

    total_removed = 0
    for layout_name in layout_names:
        rel_name = f"ppt/slideLayouts/_rels/{Path(layout_name).name}.rels"
        layout_bytes = contents[layout_name]
        rel_bytes = contents.get(rel_name)

        new_layout, new_rels, changed = pptx_cleaner.strip_gamma_from_layout(
            layout_bytes, rel_bytes
        )

        if changed:
            contents[layout_name] = new_layout
            if new_rels is not None:
                contents[rel_name] = new_rels
            elif rel_name in contents:
                del contents[rel_name]
                del infos[rel_name]
            total_removed += 1

    if total_removed == 0:
        return 0

    pptx_cleaner.write_archive(dest, infos, contents)
    return total_removed


def process_pdf(src: Path, dest: Path) -> int:
    shutil.copy(src, dest)
    return pdf_cleaner.process_pdf(dest)


def render_watermark_tool() -> None:
    st.title("🧼 Gamma Watermark Remover")
    st.write("Upload a PPTX or PDF exported from Gamma and get a clean version back.")

    uploaded_file = st.file_uploader(
        "Choose a file", type=["pptx", "pdf"], accept_multiple_files=False
    )

    if not uploaded_file:
        st.info("Upload a file to get started.")
        return

    ext = Path(uploaded_file.name).suffix.lower()
    default_output = f"{Path(uploaded_file.name).stem}-clean{ext}"
    output_name = st.text_input("New file name", value=default_output)

    if not output_name.strip():
        st.warning("Please enter a valid file name.")
        return

    status_placeholder = st.empty()

    if st.button("Remove Watermark", type="primary"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(uploaded_file.getbuffer())
            tmp_path = Path(tmp.name)

        output_path = Path(output_name)
        if not output_path.is_absolute():
            output_path = BASE_DIR / output_path

        try:
            if ext == ".pptx":
                removed = process_pptx(tmp_path, output_path)
            else:
                removed = process_pdf(tmp_path, output_path)

            if removed == 0:
                status_placeholder.warning("No Gamma watermark detected; file untouched.")
            else:
                status_placeholder.success(f"Removed {removed} watermark element(s).")
                with open(output_path, "rb") as fh:
                    data = fh.read()
                st.download_button(
                    "Download cleaned file",
                    data,
                    file_name=output_path.name,
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    if ext == ".pptx"
                    else "application/pdf",
                )
        except Exception as exc:
            status_placeholder.error(f"Failed to process file: {exc}")
        finally:
            tmp_path.unlink(missing_ok=True)


def render_iimjobs_tool() -> None:
    st.title("📄 iimjobs Applied Jobs Export")
    st.write("Enter your iimjobs credentials to export applied jobs as CSV.")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    headless = st.checkbox("Run browser headless", value=True)
    output_name = st.text_input("Output filename", value=IIMJOBS_DEFAULT_OUTPUT)

    status_placeholder = st.empty()

    if st.button("Export Applied Jobs", type="primary"):
        if not email or not password:
            status_placeholder.error("Email and password are required.")
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp_path = Path(tmp.name)

        try:
            path, count = iimjobs_exporter.export_applied_jobs(
                email=email,
                password=password,
                output_path=tmp_path,
                headless=headless,
            )
            status_placeholder.success(f"Exported {count} jobs.")
            with open(path, "rb") as fh:
                data = fh.read()
            st.download_button(
                "Download CSV",
                data,
                file_name=output_name or IIMJOBS_DEFAULT_OUTPUT,
                mime="text/csv",
            )
        except Exception as exc:
            status_placeholder.error(f"Failed to export: {exc}")
        finally:
            tmp_path.unlink(missing_ok=True)


def main() -> None:
    st.set_page_config(page_title="Automation Toolkit", page_icon="🧰", layout="centered")
    tool = st.sidebar.radio(
        "Choose tool", (TOOL_WATERMARK, TOOL_IIMJOBS), index=0
    )

    if tool == TOOL_WATERMARK:
        render_watermark_tool()
    else:
        render_iimjobs_tool()


if __name__ == "__main__":
    main()

