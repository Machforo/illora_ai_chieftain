from postprocess_and_save import finalize_and_write

# Sample raw lines (simulate what the QA generator produced)
raw_lines = [
    "30,What is the schedule for the morning activities?,Morning Magic: Sunrise Yoga; Guided bush walks; Safari drives; Breakfast.",
    "31,Can I request a packed lunch for safaris?,Yes, available on request.",
    "32,What is the contact information for the hotel's website?,www.ilora-retreats.com.",
    "33,Can I request a specific type of tea or coffee?,Yes, available upon request.",
    "34,What is the schedule for the mid-morning activities?,Koroga (self-cooking with chef); Beadwork with local women; Pottery with local artisans; Maasai spear throwing.",
    "35,Can I participate in the Village visit?,Yes, it's available in the afternoon.",
    "36,What is the schedule for the afternoon activities?,Afternoon: Photography classes; Village visit; School visit.",
    "37,Can I request a specific extension number for the phone?,Yes, available upon request.",
    "38,Can I participate in the School visit?,Yes, it's available"
]

count = finalize_and_write(raw_lines)
print(f"Parsed and saved {count} pairs.")
