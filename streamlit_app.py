import shutil
import tempfile
import os
from pathlib import Path

import streamlit as st

import export_iimjobs_applied as iimjobs_exporter
import remove_gamma_logo as pptx_cleaner
import remove_gamma_logo_pdf as pdf_cleaner
import metadata_nuke
import sakamoto_downloader
import unlock_pdf


BASE_DIR = Path(__file__).resolve().parent
TOOL_WATERMARK = "🧼 Watermark Remover"
TOOL_IIMJOBS = "💼 IIMJobs Exporter"
TOOL_METADATA = "🧹 Metadata Nuke"
TOOL_UNLOCK_PDF = "🔓 Unlock PDF"
TOOL_SAKAMOTO = "📚 Sakamoto Downloader"
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


def load_css() -> None:
    st.markdown(
        """
        <style>
        /* Main Container */
        .main {
            /* Let Streamlit handle background */
        }
        
        /* Sidebar */
        [data-testid="stSidebar"] {
            /* Let Streamlit handle background */
        }
        
        /* Headings */
        h1 {
            font-family: 'Inter', sans-serif;
            font-weight: 700;
        }
        h2, h3 {
            font-family: 'Inter', sans-serif;
        }
        
        /* Cards */
        .stCard {
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            margin-bottom: 1rem;
            border: 1px solid rgba(49, 51, 63, 0.2);
        }
        
        /* Buttons */
        .stButton button {
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-weight: 600;
            border: none;
            transition: all 0.2s ease;
        }
        
        /* Inputs */
        .stTextInput input {
            border-radius: 8px;
            padding: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_watermark_tool() -> None:
    st.markdown("<h1>🧼 Gamma Watermark Remover</h1>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='background-color: white; padding: 1.5rem; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 2rem;'>
            <p style='margin: 0; color: #666; font-size: 1.1rem;'>
                Upload a PPTX or PDF exported from Gamma and get a clean version back automatically.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Choose a file", type=["pptx", "pdf"], accept_multiple_files=False
        )

    if not uploaded_file:
        st.info("👆 Upload a file to get started.")
        return

    with col2:
        st.write("### File Details")
        ext = Path(uploaded_file.name).suffix.lower()
        st.write(f"**Type:** {ext.upper()}")
        st.write(f"**Size:** {uploaded_file.size / 1024:.1f} KB")

    st.markdown("---")
    
    default_output = f"{Path(uploaded_file.name).stem}-clean{ext}"
    
    c1, c2 = st.columns([3, 1])
    with c1:
        output_name = st.text_input("Output Filename", value=default_output)
    
    with c2:
        st.write("") # Spacer
        st.write("") # Spacer
        process_btn = st.button("✨ Remove Watermark", type="primary", use_container_width=True)

    if not output_name.strip():
        st.warning("Please enter a valid file name.")
        return

    status_placeholder = st.empty()

    if process_btn:
        with st.spinner("Processing file..."):
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
                    status_placeholder.warning("⚠️ No Gamma watermark detected; file untouched.")
                else:
                    status_placeholder.success(f"✅ Successfully removed {removed} watermark element(s)!")
                    with open(output_path, "rb") as fh:
                        data = fh.read()
                    st.download_button(
                        "⬇️ Download Cleaned File",
                        data,
                        file_name=output_path.name,
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                        if ext == ".pptx"
                        else "application/pdf",
                        use_container_width=True
                    )
            except Exception as exc:
                status_placeholder.error(f"❌ Failed to process file: {exc}")
            finally:
                tmp_path.unlink(missing_ok=True)


def render_iimjobs_tool() -> None:
    st.markdown("<h1>📄 iimjobs Applied Jobs Export</h1>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='background-color: white; padding: 1.5rem; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 2rem;'>
            <p style='margin: 0; color: #666; font-size: 1.1rem;'>
                Export your entire applied jobs history from iimjobs.com to a CSV file for analysis.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        st.subheader("🔐 Credentials")
        col1, col2 = st.columns(2)
        with col1:
            email = st.text_input("Email Address", placeholder="you@example.com")
        with col2:
            password = st.text_input("Password", type="password", placeholder="••••••••")
        
        st.caption("Your credentials are used only for this session and are not stored.")

    st.markdown("---")

    with st.container():
        st.subheader("⚙️ Configuration")
        c1, c2 = st.columns([3, 1])
        with c1:
            output_name = st.text_input("Output Filename", value=IIMJOBS_DEFAULT_OUTPUT)
        with c2:
            st.write("") # Spacer
            st.write("") # Spacer
            headless = st.checkbox("Headless Mode", value=True, help="Run browser in background")

    st.write("")
    
    status_placeholder = st.empty()
    
    if st.button("🚀 Export Applied Jobs", type="primary", use_container_width=True):
        if not email or not password:
            status_placeholder.error("⚠️ Email and password are required.")
            return

        with st.spinner("🔄 Connecting to iimjobs... (this may take a moment)"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                tmp_path = Path(tmp.name)

            try:
                path, count = iimjobs_exporter.export_applied_jobs(
                    email=email,
                    password=password,
                    output_path=tmp_path,
                    headless=headless,
                )
                status_placeholder.success(f"✅ Successfully exported {count} jobs!")
                with open(path, "rb") as fh:
                    data = fh.read()
                st.download_button(
                    "⬇️ Download CSV",
                    data,
                    file_name=output_name or IIMJOBS_DEFAULT_OUTPUT,
                    mime="text/csv",
                    use_container_width=True
                )
            except Exception as exc:
                status_placeholder.error(f"❌ Failed to export: {exc}")
            finally:
                tmp_path.unlink(missing_ok=True)



def render_metadata_nuke_tool() -> None:
    st.markdown("<h1>🧹 Metadata Nuke</h1>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='background-color: white; padding: 1.5rem; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 2rem;'>
            <p style='margin: 0; color: #666; font-size: 1.1rem;'>
                Remove hidden metadata (author, creation dates, software info) from your files for enhanced privacy.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Choose a file to scrub", type=["pptx", "pdf"], accept_multiple_files=False, key="nuke_uploader"
        )

    if not uploaded_file:
        st.info("👆 Upload a file to get started.")
        return

    with col2:
        st.write("### File Details")
        ext = Path(uploaded_file.name).suffix.lower()
        st.write(f"**Type:** {ext.upper()}")
        st.write(f"**Size:** {uploaded_file.size / 1024:.1f} KB")

    st.markdown("---")
    
    default_output = f"{Path(uploaded_file.name).stem}-nuked{ext}"
    
    c1, c2 = st.columns([3, 1])
    with c1:
        output_name = st.text_input("Output Filename", value=default_output, key="nuke_output_name")
    
    with c2:
        st.write("") # Spacer
        st.write("") # Spacer
        nuke_btn = st.button("☢️ Nuke Metadata", type="primary", use_container_width=True)

    if not output_name.strip():
        st.warning("Please enter a valid file name.")
        return

    status_placeholder = st.empty()

    if nuke_btn:
        with st.spinner("Scrubbing metadata..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(uploaded_file.getbuffer())
                tmp_path = Path(tmp.name)

            output_path = Path(output_name)
            if not output_path.is_absolute():
                output_path = BASE_DIR / output_path

            try:
                if ext == ".pptx":
                    success = metadata_nuke.nuke_pptx_metadata(tmp_path, output_path)
                else:
                    success = metadata_nuke.nuke_pdf_metadata(tmp_path, output_path)

                if success:
                    status_placeholder.success("✅ Metadata successfully nuked!")
                    with open(output_path, "rb") as fh:
                        data = fh.read()
                    st.download_button(
                        "⬇️ Download Clean File",
                        data,
                        file_name=output_path.name,
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                        if ext == ".pptx"
                        else "application/pdf",
                        use_container_width=True,
                        key="nuke_download"
                    )
                else:
                    status_placeholder.error("❌ Failed to remove metadata.")
            except Exception as exc:
                status_placeholder.error(f"❌ Error: {exc}")
            finally:
                tmp_path.unlink(missing_ok=True)


def render_unlock_pdf_tool() -> None:
    st.markdown("<h1>🔓 Unlock PDF</h1>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='background-color: white; padding: 1.5rem; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 2rem;'>
            <p style='margin: 0; color: #666; font-size: 1.1rem;'>
                Upload a password-protected PDF and enter the password to remove the encryption.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Choose a PDF file", type=["pdf"], accept_multiple_files=False, key="unlock_uploader"
        )

    if not uploaded_file:
        st.info("👆 Upload a PDF file to get started.")
        return

    with col2:
        st.write("### File Details")
        st.write(f"**Size:** {uploaded_file.size / 1024:.1f} KB")

    st.markdown("---")
    
    default_output = f"{Path(uploaded_file.name).stem}-unlocked.pdf"
    
    c1, c2 = st.columns([2, 1])
    with c1:
        password = st.text_input("PDF Password", type="password", key="pdf_password")
    
    with c2:
        output_name = st.text_input("Output Filename", value=default_output, key="unlock_output_name")

    unlock_btn = st.button("🔓 Unlock PDF", type="primary", use_container_width=True)

    if not output_name.strip():
        st.warning("Please enter a valid file name.")
        return

    status_placeholder = st.empty()

    if unlock_btn:
        if not password:
            status_placeholder.error("⚠️ Please enter the password.")
            return

        with st.spinner("Unlocking PDF..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getbuffer())
                tmp_path = Path(tmp.name)

            output_path = Path(output_name)
            if not output_path.is_absolute():
                output_path = BASE_DIR / output_path

            try:
                success, message = unlock_pdf.unlock_pdf(tmp_path, output_path, password)

                if success:
                    status_placeholder.success("✅ PDF successfully unlocked!")
                    with open(output_path, "rb") as fh:
                        data = fh.read()
                    st.download_button(
                        "⬇️ Download Unlocked PDF",
                        data,
                        file_name=output_path.name,
                        mime="application/pdf",
                        use_container_width=True,
                        key="unlock_download"
                    )
                else:
                    status_placeholder.error(f"❌ {message}")
            except Exception as exc:
                status_placeholder.error(f"❌ Error: {exc}")
            finally:
                tmp_path.unlink(missing_ok=True)


def render_sakamoto_tool() -> None:
    st.markdown("<h1>📚 Sakamoto Days Downloader</h1>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='background-color: white; padding: 1.5rem; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 2rem;'>
            <p style='margin: 0; color: #666; font-size: 1.1rem;'>
                Enter one or more URLs from <a href="https://sakamotodays.org/comic/" target="_blank">sakamotodays.org</a> to download chapters as PDFs.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if 'generated_pdfs' not in st.session_state:
        st.session_state['generated_pdfs'] = []

    urls_input = st.text_area(
        "Chapter URLs (one per line)",
        placeholder="https://sakamotodays.org/comic/sakamoto-days-chapter-121/\nhttps://sakamotodays.org/comic/sakamoto-days-chapter-122/",
        height=150,
        key="sakamoto_urls"
    )

    process_btn = st.button("📚 Download Chapters", type="primary", use_container_width=True)

    if process_btn:
        urls = [url.strip() for url in urls_input.split("\n") if url.strip()]
        if not urls:
            st.warning("Please enter at least one URL.")
            st.session_state['generated_pdfs'] = []
            return

        st.session_state['generated_pdfs'] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            for url in urls:
                with st.spinner(f"Processing {url}..."):
                    try:
                        slug = url.strip('/').split('/')[-1]
                        output_filename = slug.replace('-', '_').title() + ".pdf"
                        output_path = Path(tmpdir) / output_filename

                        sakamoto_downloader.download_and_create_pdf(url, str(output_path))

                        if output_path.exists():
                            with open(output_path, "rb") as f:
                                pdf_data = f.read()
                            st.session_state['generated_pdfs'].append({
                                "name": output_filename,
                                "data": pdf_data
                            })
                        else:
                            st.error(f"Failed to create PDF for {url}.")
                    except Exception as e:
                        st.error(f"An error occurred while processing {url}: {e}")

    if st.session_state['generated_pdfs']:
        st.markdown("---")
        st.success(f"✅ Processing complete! {len(st.session_state['generated_pdfs'])} PDF(s) are ready for download.")
        st.subheader("Download Your Files")

        for pdf_file in st.session_state['generated_pdfs']:
            st.download_button(
                label=f"⬇️ Download {pdf_file['name']}",
                data=pdf_file['data'],
                file_name=pdf_file['name'],
                mime="application/pdf",
                key=f"download_{pdf_file['name']}"
            )


def main() -> None:
    st.set_page_config(
        page_title="GammaVerse Toolkit", 
        page_icon="🚀", 
        layout="centered",
        initial_sidebar_state="expanded"
    )
    load_css()

    with st.sidebar:
        st.markdown("## 🚀 GammaVerse")
        st.markdown("---")
        st.write("### Tools")
        
        # Custom styling for radio button to look more like a menu
        tool = st.radio(
            "Select a tool:",
            (TOOL_WATERMARK, TOOL_IIMJOBS, TOOL_METADATA, TOOL_UNLOCK_PDF, TOOL_SAKAMOTO),
            index=0,
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.markdown(
            """
            <div style='font-size: 0.8rem; color: #666;'>
            Built for productivity.<br>
            v1.0.0
            </div>
            """, 
            unsafe_allow_html=True
        )

    if tool == TOOL_WATERMARK:
        render_watermark_tool()
    elif tool == TOOL_IIMJOBS:
        render_iimjobs_tool()
    elif tool == TOOL_METADATA:
        render_metadata_nuke_tool()
    elif tool == TOOL_UNLOCK_PDF:
        render_unlock_pdf_tool()
    elif tool == TOOL_SAKAMOTO:
        render_sakamoto_tool()


if __name__ == "__main__":
    main()

