from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth

import sqlalchemy
from src import database as db

with db.engine.begin() as connection: 
    result = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory"))

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
    result = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory"))
    for row in result:
        gold = row.gold

    print(wholesale_catalog)
    for row in result:
        if row.num_green_potions < 10:
            for barrel in wholesale_catalog:
                if barrel.sku == "SMALL_GREEN_BARREL":
                    buyAmt = gold//barrel.price 

    return [
        {
            "sku": "SMALL_GREEN_BARREL",
            "quantity": buyAmt,
        }
    ]

