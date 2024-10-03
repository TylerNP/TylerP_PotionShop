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
    Process available barrels for sale and returns what barrels to be bought
    """

    print(wholesale_catalog)
    #TO DO improve barrel planning logic

    plan = []
    ml_types = ["red", "green", "blue", "dark"]
    num_types = len(ml_types)
    ml_needed = [0]*num_types
    ml_available = [0]*num_types
    ml_space = [0]*num_types
    gold_threshold = 0
    usable_gold = 0
    ml_capacity = 0

    with db.engine.begin() as connection: 
        #Check to determine if can purchase
        query = connection.execute(sqlalchemy.text("SELECT ml_capacity, potion_capacity, gold FROM global_inventory"))
        for result in query:
            potion_capacity_units = result.potion_capacity
            ml_capacity_units = result.ml_capacity
            usable_gold = result.gold

        usable_gold = usable_gold-gold_threshold
        ml_per_capacity = 10000
        ml_capacity = ml_capacity_units * ml_per_capacity
        total_ml = 0
        for index in range(len(ml_types)):
            sql_to_execute = "SELECT num_%s_ml FROM global_inventory"
            ml_stored = connection.execute(sqlalchemy.text(sql_to_execute % ml_types[index])).scalar()
            ml_available[index] = ml_stored
            total_ml += ml_stored
        
        if (total_ml>=ml_capacity):
            return plan
        
        #ml Needed For Immediate Brewing
        potion_per_capacity = 50
        potion_capacity = potion_per_capacity * potion_capacity_units
        sql_to_execute = "SELECT COUNT(1) FROM potions"
        potions_available = connection.execute(sqlalchemy.text(sql_to_execute)).scalar()
        potion_threshold = potion_capacity // potions_available
        sql_to_execute = "SELECT quantity, type FROM potions WHERE quantity < %d"
        specific_pots = connection.execute(sqlalchemy.text(sql_to_execute % potion_threshold))
        for pots in specific_pots:
            for index in range(num_types):
                ml_needed[index] += pots.type[index]*(potion_threshold-pots.quantity)

    #Create Ratio Of ML to Purchase Using Min
    min = 0
    ml_count = 0
    for value in ml_needed:
        if  (value < min and value != 0) or min == 0:
            min = value
        if value != 0:
            ml_count = ml_count + 1
    ml_ratio = [ round(ml/min) for ml in ml_needed]
    ml_ratio_copy = ml_ratio.copy()

    #Filter barrels purchasable with gold split between types needed and sort by ml per gold
    desired_barrels = []
    barrel_ml_per_gold = []
    barrel_types = [[] for _ in range(num_types)]
    for barrel in wholesale_catalog:
        if barrel.price > usable_gold//ml_count:
            continue
        desired_barrels.append(barrel)
        barrel_ml_per_gold.append(barrel.ml_per_barrel//barrel.price)
    sorted_barrels = [barrel for _, barrel in sorted(zip(barrel_ml_per_gold, desired_barrels), key = lambda pair:pair[0], reverse=True)]

    #Sort Barrels By Type [R,G,B,D]
    barrel_type = 1
    for barrel in sorted_barrels:
        barrel_types[barrel.potion_type.index(barrel_type)].append(barrel)

    #determine how much space is available
    num_types_buyable = 0
    ml_can_buy = [0]*num_types
    for index in range(len(barrel_types)):
        if barrel_types[index]:
            num_types_buyable = num_types_buyable + 1
            ml_can_buy[index] = 1
    ml_threshold = (ml_capacity-total_ml)//num_types_buyable
    recalculate = False
    for index in range(num_types):
        ml_space_remain = ml_threshold-ml_available[index]
        if ml_space_remain > 0:
            ml_space[index] = ml_space_remain  
        else:
            ml_can_buy[index] = 0
            num_types_buyable = num_types_buyable - 1
            recalculate = True
        
    # Better Estimate If Necessay
    if recalculate:
        ml_threshold = (ml_capacity-total_ml)//num_types_buyable
        for index in range(len(ml_types)):
            ml_space_remain = ml_threshold-ml_available[index]
            if ml_can_buy[index] == 1:
                ml_space[index] = ml_space_remain

    # Reduce Size to Space Left
    for index in range(len(ml_types)):
        if ml_needed[index] > ml_space[index]:
            ml_needed[index] = ml_space[index]

    #Buy From Most Needed Barrel Type To Least
    type_index = ml_needed.index(max(ml_needed))
    list_of_index = [0]*num_types
    buy_count = []
    unique_barrels = []
    buy_amt = 0

    #Determine If More ml Can Be Purchased For Later use
    count = 0
    loop_count = 0
    full_loop = 4
    while True:
        count += 1
        print(f"count {count}: " + ''.join(map(str,ml_can_buy)))
        if not any(ml_can_buy):
            break
        if ml_ratio_copy[type_index] <= 0 or ml_can_buy[type_index] == 0:
            type_index = (type_index+1) % num_types
            if ml_can_buy[type_index] == 0:
                loop_count += 1
                if loop_count == full_loop:
                    break
            continue
        if list_of_index[type_index] == len(barrel_types[type_index]):
            ml_can_buy[type_index] = 0
            ml_ratio_copy[type_index] = 0
            ml_ratio[type_index] = 0
            continue
        buy_amt = 1
        barrel_to_buy = barrel_types[type_index][list_of_index[type_index]]
        print(barrel_to_buy)
        print(ml_can_buy)
        print(ml_ratio_copy)
        if (usable_gold >= barrel_to_buy.price) and (ml_needed[type_index] >= barrel_to_buy.ml_per_barrel):
            buy_amt = 1
            usable_gold = usable_gold-barrel_to_buy.price
            ml_needed[type_index] = ml_needed[type_index] - barrel_to_buy.ml_per_barrel
            if barrel_to_buy not in unique_barrels:
                unique_barrels.append(barrel_to_buy)
                buy_count.append(buy_amt)
            else:
                buy_count[unique_barrels.index(barrel_to_buy)] += buy_amt
            ml_ratio_copy[type_index] = ml_ratio_copy[type_index] - round(barrel_to_buy.ml_per_barrel/min)
            cycle_complete = True
            for ml in ml_ratio_copy:
                if ml > 0:
                    cycle_complete = False
                    break
            if cycle_complete:
                for i in range(len(ml_ratio)):
                    ml_ratio_copy[i] += ml_ratio[i]
            type_index = (type_index+1) % num_types
        else:
            list_of_index[type_index] = list_of_index[type_index] + 1
        #print(unique_barrels)

    """
    #Balance Barrel Purchases with Ratio and buying from each color first
    while not done:
        if ml_ratio_copy[type_index] <= 0:
            type_index = (type_index+1) % num_types
            continue
        done = True

        #Skip Barrel Types That Are Sold Out
        loop_count = 0
        full_loop = 4
        for _ in range(num_types):
            if list_of_index[type_index] < len(barrel_types[type_index]):
                done = False
                break
            type_index = (type_index+1) % num_types
            loop_count += 1
        if loop_count == full_loop:
            break

        #Cycle Type of Barrels Bought
        buy_amt = 1
        barrel_to_buy = barrel_types[type_index][list_of_index[type_index]]
        if (usable_gold-barrel_to_buy.price) < 0:
            list_of_index[type_index] += 1
        else:
            buy_amt = 1
            usable_gold = usable_gold-barrel_to_buy.price
            if barrel_to_buy not in unique_barrels:
                unique_barrels.append(barrel_to_buy)
                buy_count.append(buy_amt)
            else:
                buy_count[unique_barrels.index(barrel_to_buy)] += buy_amt
            ml_ratio_copy[type_index] -= round(barrel_to_buy.ml_per_barrel/min)
            cycle_complete = True
            for ml in ml_ratio_copy:
                if ml > 0:
                    cycle_complete = False
                    break
            if cycle_complete:
                for i in range(len(ml_ratio)):
                    ml_ratio_copy[i] += ml_ratio[i]
            if buy_count[unique_barrels.index(barrel_to_buy)] == barrel_to_buy.quantity:
                list_of_index[type_index] += 1
                continue
            type_index = (type_index+1)%num_types
        """        
    
    for i in range(len(unique_barrels)):
        plan.append( {"sku":unique_barrels[i].sku, "quantity": buy_count[i]} )
    print(plan)
    return plan

