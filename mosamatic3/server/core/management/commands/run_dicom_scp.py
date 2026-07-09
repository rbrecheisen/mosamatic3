import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from pynetdicom import AE, evt
from pynetdicom.sop_class import CTImageStorage
from pydicom.uid import (
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    ExplicitVRBigEndian,
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLossless,
    JPEGLSLossless,
    JPEGLSNearLossless,
    JPEG2000Lossless,
    JPEG2000,
    RLELossless,
)
from core.dicomimport.services import store_incoming_dicom_dataset
from core.dicomimport.tasks import finalize_import_if_stable

logger = logging.getLogger(__name__)

CT_TRANSFER_SYNTAXES = [
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    ExplicitVRBigEndian,

    # Common compressed CT transfer syntaxes.
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLossless,
    JPEGLSLossless,
    JPEGLSNearLossless,
    JPEG2000Lossless,
    JPEG2000,
    RLELossless,
]


def _ae_title_to_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("ascii", errors="ignore").strip()
    return str(value).strip()


def handle_store(event):
    try:
        calling_ae_title = _ae_title_to_str(event.assoc.requestor.ae_title)
        called_ae_title = _ae_title_to_str(event.assoc.acceptor.ae_title)

        session = store_incoming_dicom_dataset(
            ds=event.dataset,
            file_meta=event.file_meta,
            calling_ae_title=calling_ae_title,
            called_ae_title=called_ae_title,
        )

        finalize_import_if_stable.apply_async(
            args=[str(session.id)],
            countdown=settings.DICOM_IMPORT_STABLE_SECONDS,
            queue="tasks",
        )

        logger.info(
            "Received DICOM instance for session=%s patient_id=%s series_uid=%s",
            session.id,
            session.patient_id,
            session.series_instance_uid,
        )

        return 0x0000

    except Exception:
        logger.exception("Failed to store incoming DICOM object")
        return 0xC210


class Command(BaseCommand):
    help = "Run Mosamatic3 DICOM Storage SCP for PACS C-STORE imports."

    def handle(self, *args, **options):
        ae = AE(ae_title=settings.DICOM_SCP_AE_TITLE)

        # CT only, but accept common uncompressed and compressed CT transfer syntaxes.
        for transfer_syntax in CT_TRANSFER_SYNTAXES:
            ae.add_supported_context(CTImageStorage, [transfer_syntax])

        handlers = [
            (evt.EVT_C_STORE, handle_store),
        ]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting DICOM SCP AE={settings.DICOM_SCP_AE_TITLE} "
                f"on {settings.DICOM_SCP_HOST}:{settings.DICOM_SCP_PORT}"
            )
        )

        ae.network_timeout = 300
        ae.acse_timeout = 60
        ae.dimse_timeout = 300

        ae.start_server(
            (settings.DICOM_SCP_HOST, settings.DICOM_SCP_PORT),
            block=True,
            evt_handlers=handlers,
        )