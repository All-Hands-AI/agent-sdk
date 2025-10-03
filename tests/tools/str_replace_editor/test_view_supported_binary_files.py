import tempfile
from pathlib import Path

from openhands.tools.str_replace_editor import file_editor
from openhands.tools.str_replace_editor.definition import (
    FileEditorObservation,
)

from .conftest import assert_successful_result


def test_view_pdf_file():
    # Create a temporary PDF file with some content
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
        # Create a minimal PDF content
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Printer-Friendly Caltrain Schedule) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
299
%%EOF"""  # noqa: W291
        f.write(pdf_content)
        test_file = f.name

    try:
        result = file_editor(command="view", path=test_file)

        assert isinstance(result, FileEditorObservation)
        assert_successful_result(result)
        assert f"Here's the result of running `cat -n` on {test_file}" in result.output

        # Check for specific content present in the PDF
        assert (
            result.output is not None
            and "Printer-Friendly Caltrain Schedule" in result.output
        )
    finally:
        # Clean up the temporary file
        Path(test_file).unlink(missing_ok=True)
