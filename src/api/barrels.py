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
    barrels_sent = []

    for barrel in barrels_delivered:
        count += barrel.quantity
        gold_cost += barrel.quantity*barrel.price
        green_ml_cnt += barrel.ml_per_barrel*barrel.quantity
        barrels_sent.append( {"barrels delivered": barrel, "order_id": order_id} )
        
    with db.engine.begin() as connection: 
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET gold = gold - {gold_cost}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_ml = num_green_ml + {green_ml_cnt}"))

    return barrels_sent

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ 
    Process available barrels for sale and returns what barrels are bought
    """

     #TO DO improve barrel planning logic

    buy_amt = 0
    barrel_plan = []
    desired_barrels = []

    with db.engine.begin() as connection: 
        gold = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).scalar()
        num_green_pot = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).scalar()
        for barrel in wholesale_catalog:
            if barrel.potion_type == [0,100,0,0] and num_green_pot < 10:
                desired_barrels.append(barrel)
        for barrel in desired_barrels:
            buy_amt = gold//barrel.price
            if barrel.quantity < buy_amt:
                buy_amt = barrel.quantity
            gold -= buy_amt*barrel.price
            barrel_plan.append( {"sku": barrel.sku, "quantity": buy_amt} )
            
    return barrel_plan

