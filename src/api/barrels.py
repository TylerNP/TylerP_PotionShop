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
    """ 
    Updates the database information with the barrels bought
    """
    count = 0
    gold_cost = 0
    green_ml_cnt = 0
    for barrel in barrels_delivered:
        count += barrel.quantity
        gold_cost += barrel.quantity*barrel.price
        green_ml_cnt += barrel.ml_per_barrel*barrel.quantity
    print(barrels_delivered[0].quantity)
    with db.engine.begin() as connection: 
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET gold = gold - {gold_cost}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_ml = num_green_ml + {green_ml_cnt}"))
        connection.commit()

    return [
            {
                "barrels delivered": barrels_delivered,
                "order_id": order_id
            }
    ]

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ 
    Process available barrels for sale and returns what barrels are bought
    """

    buyAmt = 0
    barrelName = ""

    with db.engine.begin() as connection: 
        gold = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).scalar()
        numGreenPot = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).scalar()
        for barrel in wholesale_catalog:
            if gold < barrel.price:
                break
            if barrel.potion_type == [0,100,0,0] and numGreenPot < 10:
                barrelName = barrel.sku
                buyAmt = gold//barrel.price
                if barrel.quantity < buyAmt:
                    buyAmt = barrel.quantity
                    
    return [
        {
            "sku": barrelName,
            "quantity": buyAmt
        }
    ]

