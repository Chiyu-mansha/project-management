"""POD-3 local storage, PDF template and signing adapters."""

from __future__ import annotations

import hashlib
import html
import io
import os
import zipfile
import base64
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape



class LocalFileStorage:
    """Object-storage shaped adapter backed by a local directory for the MVP."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, object_key: str, content: bytes) -> str:
        target = self.root / object_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return object_key

    def get(self, object_key: str) -> bytes:
        target = self.root / object_key
        if not target.is_file() or self.root.resolve() not in target.resolve().parents:
            raise FileNotFoundError(object_key)
        return target.read_bytes()

    def url(self, object_key: str) -> str:
        return f"/api/storage/{object_key}"


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class CredentialPdfTemplate:
    """Generate a small, valid PDF certificate without a native dependency."""

    def render(self, credential: dict[str, object]) -> bytes:
        lines = [
            "POD-3 电子活动凭证",
            f"凭证编号: {credential.get('credential_no', '')}",
            f"活动: {credential.get('title', '')}",
            f"学生: {credential.get('student_id', '')}",
            f"主办方: {credential.get('organizer_name', '') or ''}",
            f"综测分值: {credential.get('comprehensive_score', '') or ''}",
            f"状态: {credential.get('status', 'ISSUED')}",
            "本凭证由校园活动平台生成，可通过凭证编号核验。",
        ]
        # Helvetica is available in every PDF reader; UTF-8 text is kept as a
        # readable metadata line while the MVP template uses escaped ASCII IDs.
        ascii_lines = [html.unescape(line).encode("ascii", "replace").decode("ascii") for line in lines]
        commands = ["BT", "/F1 18 Tf", "72 740 Td", f"({_pdf_escape(ascii_lines[0])}) Tj", "/F1 11 Tf"]
        for line in ascii_lines[1:]:
            commands.extend(["0 -32 Td", f"({_pdf_escape(line)}) Tj"])
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        ]
        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(pdf))
            pdf.extend(f"{index} 0 obj\n".encode())
            pdf.extend(obj)
            pdf.extend(b"\nendobj\n")
        xref = len(pdf)
        pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode())
        pdf.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        )
        return bytes(pdf)


class LocalSealService:
    """Development signer; production can replace this adapter with CA service."""

    provider = "LOCAL_DEMO_SEAL"

    def seal(self, pdf: bytes, *, seal_id: str, signed_by: str) -> tuple[bytes, str]:
        marker = f"\n% POD3-SEAL seal_id={seal_id} signed_by={signed_by}\n".encode()
        signed = pdf + marker
        return signed, hashlib.sha256(signed).hexdigest()


class HttpSealService:
    """Adapter for the shared electronic-signature service."""

    provider = "HTTP_SEAL_SERVICE"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def seal(self, pdf: bytes, *, seal_id: str, signed_by: str) -> tuple[bytes, str]:
        import requests

        response = requests.post(
            f"{self.base_url}/seal",
            json={
                "seal_id": seal_id,
                "signed_by": signed_by,
                "pdf_base64": base64.b64encode(pdf).decode("ascii"),
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        signed_pdf = base64.b64decode(payload["signed_pdf_base64"])
        return signed_pdf, payload.get("sha256") or hashlib.sha256(signed_pdf).hexdigest()


def build_student_bundle(files: Iterable[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, content in files:
            archive.writestr(filename, content)
    return output.getvalue()


def build_csv(rows: list[dict[str, object]]) -> bytes:
    headers = ["credential_no", "student_id", "title", "comprehensive_score", "status"]
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(str(row.get(header, "")).replace(",", " ") for header in headers))
    return ("\n".join(lines) + "\n").encode("utf-8-sig")


def build_xlsx(rows: list[dict[str, object]]) -> bytes:
    """Create a minimal standards-compliant XLSX without openpyxl."""
    headers = ["credential_no", "student_id", "title", "comprehensive_score", "status"]

    def column_name(index: int) -> str:
        name = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            name = chr(65 + remainder) + name
        return name

    values = [headers] + [[str(row.get(header, "")) for header in headers] for row in rows]
    cells = []
    for row_number, row in enumerate(values, start=1):
        parts = []
        for column_number, value in enumerate(row, start=1):
            ref = f"{column_name(column_number)}{row_number}"
            parts.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
        cells.append(f'<row r="{row_number}">' + "".join(parts) + "</row>")
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>' + "".join(cells) + "</sheetData></worksheet>"
    ).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Credentials" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return output.getvalue()
