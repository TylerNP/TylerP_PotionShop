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
    """
    Returns quantities of items in global inventory 
    """
    ml_types = ["red", "green", "blue", "dark"]
    gold = 0
    ml_in_barrels = 0
    number_of_potions = 0
    with db.engine.begin() as connection:
        gold = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).scalar()
        for i in range(len(ml_types)):
            ml_in_barrels += connection.execute(sqlalchemy.text("SELECT num_%s_ml FROM global_inventory" % ml_types[i])).scalar()
        number_of_potions = connection.execute(sqlalchemy.text("SELECT num_potions FROM global_inventory")).scalar()
    
    return {"number_of_potions": number_of_potions, "ml_in_barrels": ml_in_barrels, "gold": gold}

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """
    usable_gold = 0
    ml_total = 0
    potion_count = 0
    with db.engine.begin() as connection:
        sql_to_execute = """
                            SELECT num_red_ml, num_green_ml, num_blue_ml, num_dark_ml, 
                            gold, ml_capacity, potion_capacity, num_potions 
                            FROM global_inventory
                        """
            
        query = connection.execute(sqlalchemy.text(sql_to_execute))
        for result in query:
            divide_half = 2
            usable_gold = result.gold // divide_half
            ml_capacity = result.ml_capacity
            potion_capacity = result.potion_capacity
            potion_count = result.num_potions
            ml_total = result.num_red_ml + result.num_green_ml + result.num_blue_ml + result.num_dark_ml

    cost_per_capacity = 1000
    ml_per_capacity = 10000
    potion_per_capacity = 50
    potion_capacity_bought = 0
    ml_capacity_bought = 0

    # Only buy capacity to double storage 
    if ml_total > ml_capacity*ml_per_capacity and potion_count > potion_capacity*potion_per_capacity:
        double = 2
        ml_capacity_desired = double * ml_capacity_desired 
        potion_capacity_desired = double * ml_capacity_desired
        ml_capacity_bought = ml_capacity_desired - ml_capacity
        potion_capacity_bought = potion_capacity_desired - potion_capacity
        if usable_gold < cost_per_capacity*(ml_capacity_bought+potion_capacity_bought):
            ml_capacity_bought = 0
            potion_capacity_bought = 0
 
    print(f"Bought {potion_capacity_bought} potion_capacity and {ml_capacity_bought} ml_capacity")
    return {
        "potion_capacity": potion_capacity_bought,
        "ml_capacity": ml_capacity_bought
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

    ml_capacity_increment = capacity_purchase.ml_capacity
    potion_capacity_increment = capacity_purchase.potion_capacity
    cost_per_capacity = 1000
    total_cost = cost_per_capacity*(ml_capacity_increment+potion_capacity_increment)
    with db.engine.begin() as connection:
        sql_to_execute = """
                            UPDATE global_inventory 
                            SET gold = gold-%d,
                            ml_capacity = ml_capacity + %d,
                            potion_capacity = potion_capacity + %d
                        """
        connection.execute(sqlalchemy.text(sql_to_execute % (total_cost, ml_capacity_increment, potion_capacity_increment)))

    print(f"Used {total_cost} For {ml_capacity_increment} ml_capacity and {potion_capacity_increment} potion_capacity")
    return "OK"
