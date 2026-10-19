# S02 Important 7 UI fix report

DONE. Owned implementation changes only app/views/data_center.py and tests/test_data_center.py. No Git, core, dependency or network operations.

The uploader's deduplication token now resets only when file_uploader returns None. Removing a mounted upload preserves the current source/preview/acknowledgement; deliberate subsequent selection of identical name/bytes calls set_source again, restoring user.csv and price/decimal defaults while clearing the old preview and acknowledgement. Choosing a sample leaves the mounted upload token intact, so ordinary reruns do not silently restore the old uploaded file.

One regression uses real Streamlit AppTest with only streamlit.file_uploader mocked to return a named BytesIO, None, then the identical BytesIO. It checks initial and final visible source captions, active filename, mounted-upload sample persistence across ordinary reruns, preview/acknowledgement preservation on uploader removal, and preview/acknowledgement invalidation plus real price/decimal defaults on reselection. All 12 existing tests retained.

RED command: `.venv/bin/python -m pytest tests/test_data_center.py -q -k identical_upload_reselection_after_sample > outputs/acceptance/S02/ui_review_red_checks.txt 2>&1`
Exit 1: `1 failed, 12 deselected in 0.94s`; assertion expected user.csv but received SYNTH_dirty_data.csv. This is the intended failure, observed before production changes. Captured Streamlit bare-mode missing ScriptRunContext warning appears in failed-test logging, not a product exception.

GREEN command: `.venv/bin/python -m pytest tests/test_data_center.py -q > outputs/acceptance/S02/ui_review_green_checks.txt 2>&1`
Exit 0: `13 passed in 3.84s`, no pytest warnings. Full suite reserved for controller audit.

Limits: mocked uploader is a state-transition regression, not actual native browser file selection automation. No other finding or feature expansion. Narrow reviewer followup remains with controller.
