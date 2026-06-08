from browser_use import Agent, Browser, BrowserProfile, ChatAnthropic
from dotenv import load_dotenv
import asyncio
import csv
import time
import os
import sys

load_dotenv()

LOG_FILE = "run_log.txt"

class Tee:
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
ROWS = 2  # Set to None to process all 500 rows

SPEED_OPTIMIZATION_PROMPT = """
Speed optimization instructions:
- Be extremely concise and direct in your responses
- Get to the goal as quickly as possible
- Use multi-action sequences whenever possible to reduce steps
- Once you are done with entire process just say "I'm Done Yazan". No need to say anything else or any give any summary
"""

async def main():
    log_file = open(LOG_FILE, "a", encoding="utf-8")
    sys.stdout = Tee(log_file)

    llm = ChatAnthropic(model="claude-sonnet-4-6")
    page_extraction_model = ChatAnthropic(model="claude-haiku-4-5-20251001")

    browser_profile_info = BrowserProfile(
        minimum_wait_page_load_time=0.1,
        wait_between_actions=0.1,
        headless=False,
    )

    # Single persistent browser — login + 2FA happens only once
    browser = Browser(keep_alive=True, browser_profile=browser_profile_info, allowed_domains=["*.salesforce.com", "*.lightning.force.com"],
)
    await browser.start()

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if ROWS is not None:
        rows = rows[:ROWS]

    overall_start = time.time()
    prev_cost = 0.0
    prev_tokens = 0

    for i, row in enumerate(rows):
        task = """
Follow these steps to complete the process:
1) Go to https://appliedai.lightning.force.com/lightning/n/preempt__My_Precursive. If you are NOT already logged in, log in with the details provided then click submit. If you are asked for authentication code then wait just 5 seconds as it will be written automatically. If already logged in, skip login entirely.
2) In the middle of the page, you will see Date Navigation Control. Change the date to {date}. If you are already on the same date then ignore this step.
3) Click the "Add Row" button located in the Timesheet section.
4) Select the project {project} and if its internal project, select the phase as internal. If its Learning and development then the phase becomes internal initatives. If project is Project Pulse or Evolve, you do not select any phase.
5) Select all task categories matching same or similar tasks [{tags}] by clicking the + sign then click Add Row. If an exact task is missing then ignore it.
6) You will see Phase of the project {project} and to its right you will see "0h". Change it to {Hours} then press enter. It auto saves. This is done once only. Thats all for the process.
""".format(
            date=row["Hour Date"],
            project=row["Project"],
            tags=row["Hour Tags"],
            Hours=row["Logged Hours"],
        )

        print(f"\n--- Row {i + 1}/{len(rows)}: {row['Hour Date']} | {row['Project']} ---")
        row_start = time.time()

        agent = Agent(
            task=task,
            sensitive_data={
                'x_user': os.getenv("EMAIL"),
                'x_pass': os.getenv("PASS"),
            },
            browser=browser,  # Reuse the same browser session
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
            generate_gif=False,
            max_failures=5,
            max_actions_per_step=5,
        )

        run = await agent.run()

        print("Output: ", run.final_result())
        row_elapsed = time.time() - row_start
        s = await agent.token_cost_service.get_usage_summary()
        row_tokens = s.total_tokens - prev_tokens
        row_cost = s.total_cost - prev_cost
        prev_tokens = s.total_tokens
        prev_cost = s.total_cost
        print(f"Row {i + 1} completed in {row_elapsed:.1f}s | tokens: {row_tokens:,} | cost: ${row_cost:.4f}")

    overall_elapsed = time.time() - overall_start
    print(f"\n--- Overall ---")
    print(f"Rows processed : {len(rows)}")
    print(f"Total time     : {overall_elapsed:.1f}s")
    print(f"Total tokens   : {s.total_tokens:,}")
    print(f"Total cost     : ${s.total_cost:.4f}")

    await browser.kill()
    sys.stdout = sys.__stdout__
    log_file.close()

if __name__ == "__main__":
    asyncio.run(main())
