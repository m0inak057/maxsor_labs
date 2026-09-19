import json
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import Base, engine, get_db
from src.models import User, Ticket, Decision
from src.schemas import UserRegister, UserLogin, Token, UserOut, TicketCreate, TicketOut, DecisionOut
from src.auth import hash_password, verify_password, create_access_token, get_current_user
from src.decision import get_decision

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MaxsorLabs Support Decision API")


def _serialize_decision(decision: Decision) -> DecisionOut:
    return DecisionOut(
        id=decision.id,
        action=decision.action,
        reason=decision.reason,
        confidence=decision.confidence,
        sources=json.loads(decision.sources),
        created_at=decision.created_at,
    )


def _serialize_ticket(ticket: Ticket) -> TicketOut:
    return TicketOut(
        id=ticket.id,
        message=ticket.message,
        created_at=ticket.created_at,
        decision=_serialize_decision(ticket.decision) if ticket.decision else None,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/tickets", response_model=TicketOut, status_code=201)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = Ticket(
        user_id=current_user.id,
        message=payload.message,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    ai_decision = get_decision(payload.message)

    decision = Decision(
        ticket_id=ticket.id,
        action=ai_decision.action,
        reason=ai_decision.reason,
        confidence=ai_decision.confidence,
        sources=json.dumps(ai_decision.sources),
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    ticket.decision = decision
    return _serialize_ticket(ticket)


@app.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tickets = (
        db.query(Ticket)
        .filter(Ticket.user_id == current_user.id)
        .order_by(Ticket.created_at.desc())
        .all()
    )
    return [_serialize_ticket(t) for t in tickets]


@app.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return _serialize_ticket(ticket)
