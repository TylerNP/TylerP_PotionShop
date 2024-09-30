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
    barrels_sent = []
    ml_type = ["red", "green", "blue", "dark"]
    ml_bought = [0]*4

    for barrel in barrels_delivered:
        count += barrel.quantity
        gold_cost += barrel.quantity*barrel.price
        for index in range(len(ml_type)):
            ml_bought[index] += barrel.ml_per_barrel*barrel.quantity*barrel.potion_type[index]
        barrels_sent.append( {"barrels delivered": barrel, "order_id": order_id} )
        
    with db.engine.begin() as connection: 
        sql_to_execute = "UPDATE global_inventory SET gold = gold - %d"
        connection.execute(sqlalchemy.text(sql_to_execute % gold_cost))
        for index in range(len(ml_type)):
            sql_to_execute = "UPDATE global_inventory SET num_%s_ml = num_%s_ml + %d"
            connection.execute(sqlalchemy.text(sql_to_execute % (ml_type[index], ml_type[index], ml_bought[index])))

    for index in range(len(ml_type)):
        print("Bought %d %s ml" % (ml_bought[index], ml_type[index]))
    return barrels_sent

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ 
    Process available barrels for sale and returns what barrels are bought
    """

    print(wholesale_catalog)
    #TO DO improve barrel planning logic

    buy_amt = 0
    barrel_plan = []
    desired_barrels = []
    barrel_efficiency = []
    ml_types = ["red", "green", "blue", "dark"]
    ml_needed = [0]*4
    gold = 0

    with db.engine.begin() as connection: 
        num_pots = connection.execute(sqlalchemy.text("SELECT num_potions FROM global_inventory WHERE num_potions > 50")).scalar()
        if num_pots == 1:
            return barrel_plan
        gold = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).scalar()
        specific_pots = connection.execute(sqlalchemy.text("SELECT quantity FROM potions WHERE quantity < 10"))
        for pots in specific_pots:
            for index in range(len(ml_types)):
                ml_needed[index] += pots.type[index]*(10-pots.quantity)
        for barrel in wholesale_catalog:
            for index in range(len(ml_types)):
                if barrel.potion_type[index] == 1 and ml_needed[type] > 0:
                    desired_barrels.append(barrel)
                    barrel_efficiency.append(barrel.ml_per_barrel//barrel.price)
                    break
    sorted_barrels = [barrel for _, barrel in sorted(zip(desired_barrels,barrel_efficiency), key = lambda pair:pair[0])]
    for barrel in sorted_barrels:
        buy_amt = gold//barrel.price
        if barrel.quantity < buy_amt:
            buy_amt = barrel.quantity
        gold -= buy_amt*barrel.price
        if buy_amt > 0:
            barrel_plan.append( {"sku": barrel.sku, "quantity": buy_amt} )
            
    print(barrel_plan)
    return barrel_plan

