from typing import Any, Generic, TypeVar

from sqlalchemy.orm import Session


ModelT = TypeVar("ModelT")


class CRUDRepository(Generic[ModelT]):
    def __init__(self, session: Session, model_cls: type[ModelT]) -> None:
        self.session = session
        self.model_cls = model_cls

    def list(self) -> list[ModelT]:
        return self.session.query(self.model_cls).order_by(self.model_cls.id.asc()).all()  # type: ignore[attr-defined]

    def get(self, item_id: int) -> ModelT | None:
        return self.session.get(self.model_cls, item_id)

    def create(self, payload: dict[str, Any]) -> ModelT:
        item = self.model_cls(**payload)
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def update(self, item: ModelT, payload: dict[str, Any]) -> ModelT:
        for field, value in payload.items():
            setattr(item, field, value)
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def delete(self, item: ModelT) -> None:
        self.session.delete(item)
        self.session.commit()
