from browser_use import Agent, ChatAnthropic, BrowserProfile
from dotenv import load_dotenv
import asyncio
import csv
import time
import os
import sys

load_dotenv()

LOG_FILE = "run_log.txt"

class Tee:
    """Write to both stdout and a log file simultaneously."""
    def __init__(self, file):
        self.file = file
        self.stdout = sys.__stdout__

    def write(self, data):
        self.stdout.write(data)
        self.file.write(data)

    def flush(self):
        self.stdout.flush()
        self.file.flush()

CSV_FILE = "Timely Data - Yazan - Timely Data - Yazan.csv"
ROWS = 2  

async def main():
    log_file = open(LOG_FILE, "a", encoding="utf-8")
    sys.stdout = Tee(log_file)


    # Speed optimization instructions for the model
    SPEED_OPTIMIZATION_PROMPT = """
    Speed optimization instructions:
    - Be extremely concise and direct in your responses
    - Get to the goal as quickly as possible
    - Use multi-action sequences whenever possible to reduce steps
    - Once you are done with entire process just say "I'm Done Yazan". No need to say anything else or any give any summary
    """

    # 2. Create speed-optimized browser profile
    browser_profile_info = BrowserProfile(
    minimum_wait_page_load_time=0.1,
    wait_between_actions=0.1,
    headless=False)

    llm = ChatAnthropic(model = "claude-sonnet-4-6")
    page_extraction_model = ChatAnthropic(model="claude-haiku-4-5-20251001")

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if ROWS is not None:
        rows = rows[:ROWS]

    overall_start = time.time()

    for i, row in enumerate(rows):
        task = """
    Follow these steps to complete the process:
    1) https://appliedai.lightning.force.com/lightning/n/preempt__My_Precursive. Log in with the details provided then click submit. If you are asked for authentication code then wait just 5 seconds as it will be written automatically.
    2) In the middle of the page, you will see Date Navigation Control. Change the date to {date}. If you are already on the same date then ignore this step
    3) Click the "Add Row" button located in the Timesheet section
    4) Select the project {project} and if its internal project, select the phase as internal. If its Learning and development then the phase becomes internal initatives. If project is Project Pulse or Evolve, you do not select any phase.
    5) Select all task categories matching exact same tasks [{tags}] by clicking the + sign then click Add Row. If an exact task is missing then ignore it.
    6) You will see Phase of the project {project} and to its right u will see "0h". Change it to {Hours} then press enter. It auto saves. This is done once only. Thats all for the process.
""".format(
            date=row["Hour Date"],
            project=row["Project"],
            tags=row["Hour Tags"],
            Hours=row["Logged Hours"],
        )

        print(f"\n--- Row {i + 1}/{len(rows)}: {row['Hour Date']} | {row['Project']} ---")
        row_start = time.time()

        agent = Agent(task=task,
                      sensitive_data={
                          'x_user': os.getenv("EMAIL"),
                          'x_pass': os.getenv("PASS")},
                      browser_profile=browser_profile_info,
                      llm=llm,
                       use_vision=True,
                       vision_detail_level="auto",
                       page_extraction_llm=page_extraction_model,
                       use_thinking=False,
                       flash_mode=True,
                       extend_system_message=SPEED_OPTIMIZATION_PROMPT,
                       max_history_items=None,
                       directly_open_url=True,
                       calculate_cost=True,
                       generate_gif=True, #Might do it False
                       max_failures=5,
                       max_actions_per_step=5)

        run = await agent.run()

        print("Output: ", run.final_result())

        row_elapsed = time.time() - row_start
        print(f"Row {i + 1} completed in {row_elapsed:.1f}s")

    overall_elapsed = time.time() - overall_start
    print(f"\nAll {len(rows)} rows processed in {overall_elapsed:.1f}s")

    sys.stdout = sys.__stdout__
    log_file.close()

if __name__ == "__main__":
    asyncio.run(main())
