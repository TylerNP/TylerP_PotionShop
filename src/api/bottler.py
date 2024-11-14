from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth

import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    """ 
    Update database values for ml and potions
    """
    ml_used = [0]*4
    ml_red = []
    ml_green = []
    ml_blue = []
    ml_dark = []
    quantities = []
    for potion in potions_delivered:
        quantities.append(potion.quantity)
        ml_red.append(potion.potion_type[0])
        ml_green.append(potion.potion_type[1])
        ml_blue.append(potion.potion_type[2])
        ml_dark.append(potion.potion_type[3])
        ml_used[0] += potion.potion_type[0]*potion.quantity
        ml_used[1] += potion.potion_type[1]*potion.quantity
        ml_used[2] += potion.potion_type[2]*potion.quantity
        ml_used[3] += potion.potion_type[3]*potion.quantity
    with db.engine.begin() as connection:
        values = {
                    "quantities":quantities, 
                    "ml_red":ml_red, 
                    "ml_green":ml_green, 
                    "ml_blue":ml_blue, 
                    "ml_dark":ml_dark,
                    "order_id":order_id
                }
        sql_to_execute = """
                            UPDATE potions
                            SET quantity = quantity + p.pot_quantity
                            FROM (SELECT 
                            UNNEST(:quantities) AS pot_quantity,
                            UNNEST(:ml_red) AS pot_red,
                            UNNEST(:ml_green) AS pot_green,
                            UNNEST(:ml_blue) AS pot_blue,
                            UNNEST(:ml_dark) AS pot_dark)
                            AS p
                            WHERE red = p.pot_red
                            AND green = p.pot_green
                            AND blue = p.pot_blue
                            And dark = p.pot_dark
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            SELECT 'Brewed: ' || p.pot_quantity || ' ' || potions.sku || ', ' as details
                            FROM potions, (
                                SELECT UNNEST(:quantities) AS pot_quantity,
                                UNNEST(:ml_red) AS pot_red,
                                UNNEST(:ml_green) AS pot_green,
                                UNNEST(:ml_blue) AS pot_blue,
                                UNNEST(:ml_dark) AS pot_dark)
                                AS p
                            WHERE red = p.pot_red
                            AND green = p.pot_green
                            AND blue = p.pot_blue
                            And dark = p.pot_dark
                        """
        texts = connection.execute(sqlalchemy.text(sql_to_execute), values)
        concat_text = ""
        for text in texts:
            concat_text = concat_text + text.details
        values["text"] = concat_text
        sql_to_execute = """
                            INSERT INTO transactions (description, time_id, order_id)
                            VALUES (:text, (SELECT MAX(time.id) FROM time LIMIT 1), :order_id)
                            RETURNING id
                        """
        transaction_id = connection.execute(sqlalchemy.text(sql_to_execute), values).scalar()
        values["transaction_id"] = transaction_id
        sql_to_execute = """
                            INSERT INTO potion_ledgers (sku, quantity, transaction_id)
                            SELECT p.sku, q.pot_quantity, :transaction_id 
                            FROM potions AS p, 
                                (SELECT UNNEST(:ml_red) AS pot_red, 
                                UNNEST(:ml_green) AS pot_green, 
                                UNNEST(:ml_blue) AS pot_blue, 
                                UNNEST(:ml_dark) AS pot_dark, 
                                UNNEST(:quantities) AS pot_quantity) AS q
                            WHERE q.pot_red = p.red 
                            AND q.pot_green = p.green
                            AND q.pot_blue = p.blue
                            AND q.pot_dark = p.dark
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        values = {
            "red": ml_used[0],
            "green":ml_used[1],
            "blue":ml_used[2],
            "dark":ml_used[3],
            "transaction_id":transaction_id
        }
        sql_to_execute = """
                            INSERT INTO ml_ledgers (num_red_ml, num_green_ml, num_blue_ml, num_dark_ml, transaction_id)
                            VALUES (-1*:red, -1*:green, -1*:blue, -1*:dark, :transaction_id)
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
    print("used %d mls" % (ml_used[0]+ml_used[1]+ml_used[2]+ml_used[3]))
    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Determine what potions to brew from remaining ml 
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.
    ml_available = [0]*4
    unique_potions = []
    potion_brew_amount = []
    potion_storage_left = 0

    update_potion_brew_list()
    with db.engine.begin() as connection:
        try:
            connection.execute(sqlalchemy.text("SELECT 1 FROM potions WHERE brew = TRUE LIMIT 1")).scalar_one()
        except sqlalchemy.exc.NoResultFound:
            return []

        sql_to_execute = """
            WITH pot_split AS (
                SELECT 
                    (SELECT potion_capacity FROM global_inventory) *50/ (SELECT COUNT(1) FROM potions WHERE brew = TRUE) AS threshold
            ),
            pot_threshold AS (
                SELECT 
                CASE
                    WHEN pot_split.threshold <  parameters.potion_cap THEN pot_split.threshold 
                ELSE 
                    parameters.potion_cap
                END AS threshold
                FROM pot_split, parameters
            ),
            pot_remaining AS (
                SELECT
                    (SELECT potion_capacity FROM global_inventory) *50- (SELECT SUM(quantity) FROM potion_ledgers) AS stored
            )

            SELECT 
                SUM(ml_ledgers.num_red_ml)::int AS num_red_ml,
                SUM(ml_ledgers.num_green_ml)::int AS num_green_ml,
                SUM(ml_ledgers.num_blue_ml)::int AS num_blue_ml,
                SUM(ml_ledgers.num_dark_ml)::int AS num_dark_ml,
                (SELECT pot_threshold.threshold FROM pot_threshold) AS threshold,
                (SELECT pot_remaining.stored::int FROM pot_remaining) AS remaining_storage
            FROM 
                ml_ledgers
        """
        results = connection.execute(sqlalchemy.text(sql_to_execute))
        potion_threshold = 0
        potion_storage_left = 0
        for result in results:
            ml_available[0] = result.num_red_ml
            ml_available[1] = result.num_green_ml
            ml_available[2] = result.num_blue_ml
            ml_available[3] = result.num_dark_ml
            potion_threshold = result.threshold
            potion_storage_left = result.remaining_storage

        sql_to_execute = """
                            SELECT red, green, blue, dark, quantity 
                            FROM potions 
                            WHERE quantity < :quantity 
                            AND red <= :red_amt 
                            AND green <= :green_amt 
                            AND blue <= :blue_amt 
                            AND dark <= :dark_amt 
                            and brew = TRUE
                            ORDER BY quantity ASC, price DESC
                        """
        values = [
                    {
                        "quantity":potion_threshold, 
                        "red_amt":ml_available[0], 
                        "green_amt":ml_available[1], 
                        "blue_amt":ml_available[2], 
                        "dark_amt":ml_available[3]
                    }
                ]
        potions_brewable = connection.execute(sqlalchemy.text(sql_to_execute), values)
        for potion in potions_brewable:
            unique_potions.append([potion.red, potion.green, potion.blue, potion.dark])
            desired_potion_brew_count = potion_threshold-potion.quantity
            potion_brew_amount.append(desired_potion_brew_count)

    return bottle_plan_calculation(potion_brew_amount, ml_available, unique_potions, potion_storage_left)

def bottle_plan_calculation(
                                potion_brew_amount : list[int], 
                                ml_available : list[int], 
                                unique_potions : list[list[int]], 
                                potion_storage_left : int
                            ) -> list[dict[str, any]]:
    """
    Determines how much of each potion to brew
    """
    if not potion_brew_amount or not any(potion_brew_amount):
        return []
    plan = []
    potion_count = len(unique_potions)
    potion_unavailable = [0]*potion_count
    unique_potion_counts = [0]*potion_count
    min = potion_brew_amount[-1]
    potion_brew_ratio = [ round(quantity/min) for quantity in potion_brew_amount]
    brew_ratio_copy = potion_brew_ratio.copy()
    ml_used = ml_available.copy()

    potion_index = 0
    count = 0
    while potion_storage_left > 0 and not all (potion_unavailable):
        count += 1
        if not any(brew_ratio_copy):
            brew_ratio_copy = potion_brew_ratio.copy()
        if brew_ratio_copy[potion_index] == 0 or potion_unavailable[potion_index] == 1:
            potion_index = (potion_index+1)%potion_count
        ml_leftover = [ml_available[index]-unique_potions[potion_index][index] for index in range(len(ml_available))]
        if any(ml < 0 for ml in ml_leftover) or potion_brew_amount[potion_index] == unique_potion_counts[potion_index]:
            potion_unavailable[potion_index] = 1
            potion_brew_ratio[potion_index] = 0
            brew_ratio_copy[potion_index] = 0
            continue
        potion_storage_left  -= 1
        unique_potion_counts[potion_index] += 1
        brew_ratio_copy[potion_index] -= 1
        ml_available = [ml for ml in ml_leftover]
        potion_index = (potion_index+1)%potion_count

    print(f"Looped: {count} Times") 
    for i in range(len(unique_potions)):
        if unique_potion_counts[i] == 0:
            continue
        print({"potion_type": unique_potions[i], "quantity": unique_potion_counts[i]})
        plan.append( {"potion_type": unique_potions[i], "quantity": unique_potion_counts[i]} )

    ml_types = ["red", "green", "blue", "dark"]
    for index in range(len(ml_types)):
        print(f"{ml_types[index]} used {ml_used[index]-ml_available[index]}")
    return plan

def update_potion_brew_list() -> None:
    """
    Use Current Time To Determine Which Potion To Brew For Next Tick
    Find And Set Potions to Brew For Potions That Are Popular For Next Tick/ 2 Ticks
    """
    print("Updated Potion Brew List")
    #Determine if plan should be updated (whenever the next day is about to occur)
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text("UPDATE potions SET brew = False"))
        sql_to_execute = """
            WITH time_info AS (
                SELECT time.id, time.day, time.hour FROM time ORDER BY time.id DESC LIMIT 1
            ), next_days AS (
                SELECT 
                    next_day.day AS curr_day,
                    sj.day AS next_day 
                FROM 
                    next_day 
                JOIN 
                    next_day AS sj ON next_day.next_day_id = sj.id
                JOIN
                    time_info ON next_day.day = time_info.day
            ), day_for_plan AS (
                SELECT 
                    CASE 
                        WHEN time_info.hour = 22 THEN next_days.next_day
                        ELSE next_days.curr_day
                    END AS day
                FROM 
                    time_info, 
                    next_days
            ), time_range AS (
                SELECT
                    time.id
                FROM 
                    time
                JOIN 
                    day_for_plan ON time.day = day_for_plan.day
                ORDER BY 
                    time.id DESC
                LIMIT 12
                OFFSET 1
            ), pots_sold AS (
                SELECT
                    potions.sku,
                    SUM(-1*potion_ledgers.quantity) AS amt
                FROM
                    potion_ledgers
                JOIN 
                    potions ON potion_ledgers.sku = potions.sku
                JOIN 
                    transactions ON potion_ledgers.transaction_id = transactions.id
                JOIN
                    time_range ON transactions.time_id = time_range.id
                WHERE
                    potions.price >= 10 -- Unwanted potions are set under 10
                    AND potion_ledgers.quantity < 0
                GROUP BY
                    potions.sku
                ORDER BY
                    amt DESC
                LIMIT 6
            )

            UPDATE 
                potions
            SET 
                brew = True
            FROM 
                pots_sold
            WHERE 
                potions.sku = pots_sold.sku;
        """
        connection.execute(sqlalchemy.text(sql_to_execute))

if __name__ == "__main__":
    print("Ran bottler.py")
    print(get_bottle_plan())
    #update_potion_brew_list()