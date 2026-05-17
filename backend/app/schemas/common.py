from enum import StrEnum


class RenderJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class RenderStepKind(StrEnum):
    VALIDATE = "validate"
    KEYFRAME = "keyframe"
    VIDEO = "video"
    VOICE = "voice"
    OVERLAY = "overlay"
    MUX = "mux"
    EXPORT = "export"
    ANALYTICS = "analytics"


class AssetKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    WORKFLOW = "workflow"
    SCREENSHOT = "screenshot"
    PROMPT = "prompt"
    LOG = "log"
    JSON = "json"
