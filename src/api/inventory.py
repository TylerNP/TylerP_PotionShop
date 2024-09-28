from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math

import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.get("/audit")
def get_inventory():
    """ """

    gold = 0
    ml_in_barrels = 0
    number_of_potions = 0
    with db.engine.begin() as connection:
        gold = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).scalar()
        ml_in_barrels = connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory")).scalar()
        number_of_potions = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).scalar()

    
    return {"number_of_potions": number_of_potions, "ml_in_barrels": ml_in_barrels, "gold": gold}

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    return {
        "potion_capacity": 0,
        "ml_capacity": 0
        }

class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int

# Gets called once a day
@router.post("/deliver/{order_id}")
def deliver_capacity_plan(capacity_purchase : CapacityPurchase, order_id: int):
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    return "OK"
