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
        values = {
                        "gold_cost":gold_cost, 
                        "red":ml_bought[0], 
                        "green":ml_bought[1], 
                        "blue":ml_bought[2], 
                        "dark":ml_bought[3],
                        "order_id":order_id,
                }
        sql_to_execute = """
                            INSERT INTO transactions (description, time_id)
                            VALUES (
                                    'Bought ' ||  
                                    :red || ' red ml ' || 
                                    :green || ' green ml ' || 
                                    :blue || ' blue ml ' || 
                                    :dark || ' dark ml for ' || 
                                    :gold_cost, 
                                    (SELECT time.id FROM time ORDER BY time.id DESC LIMIT 1)
                                    ) 
                            RETURNING id
                        """
        values["transaction_id"] = connection.execute(sqlalchemy.text(sql_to_execute), values).scalar()
        sql_to_execute = """
                            INSERT INTO ml_ledgers (num_red_ml, num_green_ml, num_blue_ml, num_dark_ml, order_id, transaction_id)
                            VALUES (:red, :green, :blue, :dark, :order_id, :transaction_id)
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            INSERT INTO gold_ledgers (gold, transaction_id)
                            VALUES (:gold_cost, :transaction_id)
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            UPDATE global_inventory 
                            SET gold = gold - :gold_cost,
                            num_red_ml = num_red_ml + :red,
                            num_green_ml = num_green_ml + :green,
                            num_blue_ml = num_blue_ml + :blue,
                            num_dark_ml = num_dark_ml + :dark
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values) 
    for index in range(len(ml_type)):
        print("Bought %d %s ml" % (ml_bought[index], ml_type[index]))
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ 
    Process available barrels for sale and returns what barrels to be bought
    """

    print(wholesale_catalog)
    #TO DO improve barrel planning logic

    usable_gold = 0
    ml_capacity = 0
    num_types = 4
    ml_needed = [0]*num_types
    ml_available = [0]*num_types
    ml_stored = [0]*4

    with db.engine.begin() as connection: 
        #Check to determine if can purchase
        sql_to_execute = """
                            SELECT (10000*ml_capacity) AS capacity, gold, num_red_ml, 
                                num_green_ml, num_blue_ml, num_dark_ml 
                            FROM global_inventory
                        """
        query = connection.execute(sqlalchemy.text(sql_to_execute))
        for result in query:
            ml_capacity = result.capacity
            usable_gold = result.gold
            ml_stored[0] = result.num_red_ml
            ml_stored[1] = result.num_green_ml
            ml_stored[2] = result.num_blue_ml
            ml_stored[3] = result.num_dark_ml
        
        #ml Needed For Immediate Brewing
        sql_to_execute = """
                        SELECT result.threshold, quantity, red, green, blue, dark 
                        FROM potions, (
                            SELECT (potion_capacity * 50 / (
                                SELECT COUNT(1) 
                                FROM potions 
                                WHERE brew = TRUE)) AS threshold 
                            FROM global_inventory) AS result
                        WHERE brew = TRUE 
                        AND quantity < result.threshold
                    """
        specific_pots = connection.execute(sqlalchemy.text(sql_to_execute))
        for pots in specific_pots:
            ml_needed[0] += pots.red*(pots.threshold-pots.quantity)
            ml_needed[1] += pots.green*(pots.threshold-pots.quantity)
            ml_needed[2] += pots.blue*(pots.threshold-pots.quantity)
            ml_needed[3] += pots.dark*(pots.threshold-pots.quantity)

    return barrel_plan_calculation(wholesale_catalog, ml_needed, ml_available, ml_stored, usable_gold, ml_capacity)

def barrel_plan_calculation(
                                wholesale_catalog : list[Barrel], 
                                ml_needed : list[int], 
                                ml_available : list[int], 
                                ml_stored : list[int],
                                usable_gold : int,
                                ml_capacity : int
                            ) -> dict[str, any]:
    plan = []
    num_types = 4
    ml_space = [0]*num_types
    ml_count = 0
    overflow_count = 0
    remaining_ml_threshold = 0
    gold_threshold = 0
    
    usable_gold = usable_gold-gold_threshold
    ml_threshold = ml_capacity//num_types
    total_ml = 0
    over_threshold = False
    for index in range(len(ml_needed)):
        if ml_stored[index] > ml_threshold:
            over_threshold = True
            overflow_count = overflow_count + 1
        ml_available[index] = ml_stored[index]
        total_ml += ml_stored[index]
    
    if (total_ml>=ml_capacity):
        return plan
    
    if over_threshold:
        remaining_ml_threshold = (ml_capacity-total_ml)
    

    for value in ml_needed:
        if value != 0:
            ml_count = ml_count + 1
    if ml_count == 0:
        ml_count = num_types

    #Filter barrels purchasable with gold split between types possible needed and sort by ml per gold
    desired_barrels = []
    barrel_ml_per_gold = []
    barrel_types = [[] for _ in range(num_types)]
    small_gold = 500 #gold for large barrel (red/green) 
    if usable_gold < small_gold:
        ml_count = 1
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
    ml_can_buy = [0]*num_types
    not_buyable_count = 0
    for index in range(num_types):
        if len(barrel_types[index]) > 0:
            ml_can_buy[index] = 1
        else:
            not_buyable_count = not_buyable_count + 1
    ml_max = ml_threshold
    if overflow_count > 0:
        #Trys to Refill the low values as fast as possible
        if (num_types-overflow_count-not_buyable_count) == 0:
            return plan
        ml_max = remaining_ml_threshold // (num_types-overflow_count-not_buyable_count)
    for index in range(num_types):
        ml_space_remain = ml_max - ml_available[index]
        if ml_space_remain > 0:
            ml_space[index] = ml_space_remain  
        else:
            ml_can_buy[index] = 0

    # Takes Dotproduct of ml_needed and ml_space and normalize to create weights for buying
    normal = 0
    make_int = 10
    for i in range(len(ml_needed)):
        normal += ml_needed[i]*ml_space[i]
    if normal == 0:
        normal = 1
    ml_ratio = [0]*4
    for i in range(len(ml_needed)):
        if ml_can_buy[i] == 0:
            ml_ratio[i] = 0
            continue
        # Ensure To Refill Stock Even
        if (ml_needed[i] == 0 and ml_space[i] > 0):
            ml_ratio[i] = 1
        else:
            ml_ratio[i] = round(ml_needed[i]*ml_space[i]*make_int/normal)
    ml_ratio_copy = ml_ratio.copy()
    max_index = ml_ratio.index(max(ml_ratio))
    type_index = max_index
    list_of_index = [0]*num_types
    buy_count = []
    unique_barrels = []

    #Determine If More ml Can Be Purchased For Later use
    count = 0
    while True:
        count += 1
        if not any(ml_can_buy):
            break
        cycle_complete = True
        for ml in ml_ratio_copy:
            if ml > 0:
                cycle_complete = False
                break
        #REMOVE ONCE FIXED
        #==========================#
        no_more = 0
        if cycle_complete:
            for i in range(num_types):
                ml_ratio_copy[i] = ml_ratio_copy[i] + ml_ratio[i]
                if ml_ratio_copy[i] == 0:
                    no_more += 1
            type_index = max_index
        if no_more == num_types:
            break
        #==========================#
        if ml_ratio_copy[type_index] <= 0 or ml_can_buy[type_index] == 0:
            type_index = (type_index+1) % num_types
            continue
        if list_of_index[type_index] >= len(barrel_types[type_index]):
            ml_can_buy[type_index] = 0
            ml_ratio_copy[type_index] = 0
            ml_ratio[type_index] = 0
            continue
        barrel_to_buy = barrel_types[type_index][list_of_index[type_index]]
        if (usable_gold < barrel_to_buy.price) or (ml_space[type_index] < barrel_to_buy.ml_per_barrel):
            list_of_index[type_index] = list_of_index[type_index] + 1
            continue   
        buy_amt = 1
        usable_gold = usable_gold-barrel_to_buy.price
        ml_space[type_index] = ml_space[type_index] - barrel_to_buy.ml_per_barrel
        if barrel_to_buy not in unique_barrels:
            unique_barrels.append(barrel_to_buy)
            buy_count.append(buy_amt)
        else:
            new_quantity = buy_count[unique_barrels.index(barrel_to_buy)] + buy_amt
            if new_quantity > barrel_to_buy.quantity:
                list_of_index[type_index] = list_of_index[type_index] + 1
                continue
            buy_count[unique_barrels.index(barrel_to_buy)] = new_quantity
        relative_change = round(barrel_to_buy.ml_per_barrel*make_int/normal)
        if relative_change < buy_amt:
            relative_change = buy_amt
        ml_ratio_copy[type_index] = ml_ratio_copy[type_index] - relative_change
        type_index = (type_index+1) % num_types 
    
    print(count)
    for i in range(len(unique_barrels)):
        plan.append( {"sku":unique_barrels[i].sku, "quantity": buy_count[i]} )
    print(plan)
    return plan

if __name__ == "__main__":
    print("Ran barrels.py")

