from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth

import sqlalchemy
from src import database as db

with db.engine.begin() as connection: 
    result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory")).scalar()

router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)

class Barrel(BaseModel):
    sku: str

    ml_per_barrel: int
    potion_type: list[int]
    price: int

    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_barrels(barrels_delivered: list[Barrel], order_id: int):
    """ """
    print(f"barrels delievered: {barrels_delivered} order_id: {order_id}")

    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ 
    Process available plan, 
    Then, buy when low on potions
    """
    buyAmt = 0
    gold = result.gold

    print(wholesale_catalog)
    if result.num_green_potions < 10:
        for barrel in wholesale_catalog:
            if barrel.sku == "SMALL_GREEN_BARREL":
                buyAmt = gold//barrel.price 
                if buyAmt == 0:
                    buyAmt = 1

    return [
        {
            "sku": "SMALL_GREEN_BARREL",
            "quantity": buyAmt,
        }
    ]

