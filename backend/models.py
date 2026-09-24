import re
from datetime import date
from typing import Literal

from pydantic import EmailStr, Field, model_validator, field_validator
from core import Input


class Register(Input):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    mobile: str = Field(pattern=r'^\+?[0-9]{10,15}$')
    password: str = Field(min_length=12, max_length=128)

    @field_validator('email')
    @classmethod
    def lower_email(cls, value):
        return value.lower()

    @field_validator('mobile', mode='before')
    @classmethod
    def normalize_mobile(cls, value):
        cleaned = re.sub(r'[\s()\-]', '', str(value))
        if not re.fullmatch(r'\+?[0-9]{10,15}', cleaned):
            raise ValueError('Enter a valid mobile number with 10–15 digits')
        digits = cleaned.lstrip('+')
        return '+91' + digits if len(digits) == 10 else '+' + digits


class Login(Input):
    identifier: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=128)
    portal: Literal['passenger', 'admin', 'driver'] = 'passenger'


class Staff(Register):
    role: Literal['driver', 'admin'] = 'driver'
    license: str = Field(default='', max_length=80)


class Bus(Input):
    name: str = Field(min_length=2, max_length=80)
    number: str = Field(min_length=3, max_length=24)
    operator: str = Field(min_length=2, max_length=80)
    type: Literal['Seater', 'Sleeper', 'Seater + Sleeper'] = 'Seater'
    ac: bool = True
    amenities: list[str] = Field(default_factory=list, max_length=12)
    active: bool = True

    @field_validator('number')
    @classmethod
    def normalize_number(cls, value):
        return value.upper()


class Seat(Input):
    id: str = Field(min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    label: str = Field(min_length=1, max_length=8)
    deck: Literal['lower', 'upper'] = 'lower'
    row: int = Field(ge=0, le=23)
    col: int = Field(ge=0, le=9)
    row_span: int = Field(default=1, ge=1, le=3)
    col_span: int = Field(default=1, ge=1, le=3)
    type: Literal['seat', 'berth', 'driver', 'aisle'] = 'seat'
    price: int = Field(default=500, ge=0, le=100000)
    status: Literal['AVAILABLE', 'BLOCKED', 'INACTIVE'] = 'AVAILABLE'
    ladies: bool = False


class Layout(Input):
    rows: int = Field(ge=2, le=24)
    columns: int = Field(ge=3, le=10)
    decks: list[Literal['lower', 'upper']] = Field(min_length=1, max_length=2)
    seats: list[Seat] = Field(default_factory=list, max_length=180)

    @model_validator(mode='after')
    def validate_coordinates(self):
        if len(set(self.decks)) != len(self.decks) or 'lower' not in self.decks:
            raise ValueError('Include a single lower deck and optional upper deck')
        occupied, labels, ids = set(), set(), set()
        drivers = 0
        for seat in self.seats:
            if seat.id in ids:
                raise ValueError('Seat identifiers must be unique')
            ids.add(seat.id)
            if seat.deck not in self.decks:
                raise ValueError('Seat deck must be enabled')
            if seat.type in ['seat', 'berth']:
                if seat.label in labels:
                    raise ValueError('Seat and berth numbers must be unique across decks')
                if seat.price < 1:
                    raise ValueError('A seat or berth needs a positive fare')
                labels.add(seat.label)
            if seat.type == 'driver':
                drivers += 1
                if seat.deck != 'lower':
                    raise ValueError('Driver cabin must be on lower deck')
            for row in range(seat.row, seat.row + seat.row_span):
                for col in range(seat.col, seat.col + seat.col_span):
                    if row >= self.rows or col >= self.columns:
                        raise ValueError('Element is outside the floor plan')
                    cell = (seat.deck, row, col)
                    if cell in occupied:
                        raise ValueError('Layout elements must not overlap')
                    occupied.add(cell)
        if drivers > 1:
            raise ValueError('Only one driver cabin is allowed')
        return self


class Route(Input):
    source: str = Field(min_length=2, max_length=80)
    destination: str = Field(min_length=2, max_length=80)
    distance_km: int = Field(ge=1, le=10000)
    duration_minutes: int = Field(ge=1, le=10080)
    stops: list[str] = Field(default_factory=list, max_length=50)
    boarding_points: list[str] = Field(min_length=1, max_length=30)
    dropping_points: list[str] = Field(min_length=1, max_length=30)
    active: bool = True

    @model_validator(mode='after')
    def different_cities(self):
        if self.source.casefold() == self.destination.casefold():
            raise ValueError('Source and destination must be different')
        for points in [self.stops, self.boarding_points, self.dropping_points]:
            if any(not p.strip() or len(p) > 100 for p in points):
                raise ValueError('Stops and boarding/dropping points must be named')
        return self


class Trip(Input):
    bus_id: str
    route_id: str
    driver_id: str
    date: date
    departure: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    convenience_fee: int = Field(default=0, ge=0, le=10000)
    published: bool = False


class Toggle(Input):
    active: bool


class Publish(Input):
    published: bool


class Hold(Input):
    seat_ids: list[str] = Field(min_length=1, max_length=6)


class Passenger(Input):
    name: str = Field(min_length=2, max_length=80)
    age: int = Field(ge=1, le=120)
    gender: Literal['Female', 'Male', 'Other']
    seat_id: str


class Reservation(Input):
    trip_id: str
    hold_id: str
    passengers: list[Passenger] = Field(min_length=1, max_length=6)
    boarding_point: str
    dropping_point: str


class Offer(Input):
    title: str = Field(min_length=3, max_length=80)
    code: str = Field(min_length=3, max_length=20, pattern=r'^[A-Z0-9]+$')
    description: str = Field(min_length=5, max_length=600)
    discount_percent: int = Field(ge=1, le=100)
    minimum_amount: int = Field(default=0, ge=0)
    maximum_discount: int = Field(ge=1)
    valid_until: date
    active: bool = True


class Support(Input):
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=10, max_length=2000)


class SupportReply(Input):
    reply: str = Field(min_length=1, max_length=2000)
    status: Literal['OPEN', 'IN_PROGRESS', 'RESOLVED']