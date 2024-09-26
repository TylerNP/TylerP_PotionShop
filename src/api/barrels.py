from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth

import sqlalchemy
from src import database as db

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
    potCnt = 0
    for barrel in barrels_delivered:
        potCnt += barrel.quantity
    print(f"barrels delievered: {potCnt} order_id: {order_id}")

    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ 
    Process available barrels for sale and buy when low on potions
    """

    buyAmt = 1

    with db.engine.begin() as connection: 
        gold = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).scalar()
        numGreenPot = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).scalar()
        price = 0
        if numGreenPot < 10:
            for barrel in wholesale_catalog:
                if barrel.sku == "SMALL_GREEN_BARREL":
                    connection.execute(sqlalchemy.text("UPDATE global_inveotyr SET gold = 0"))
                    buyAmt = gold//barrel.price 
                    price = barrel.price
                    if barrel.quantity < buyAmt:
                        buyAmt = barrel.quantity
                    if gold < barrel.price:
                        buyAmt = 1

        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET gold = {gold-buyAmt*price}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_potions = {numGreenPot+buyAmt}"))

    print(wholesale_catalog)
    

    return [
        {
            "sku": "SMALL_GREEN_BARREL",
            "quantity": buyAmt,
        }
    ]

