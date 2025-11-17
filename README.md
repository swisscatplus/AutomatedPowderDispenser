# Automated Powder Sampler

This project provides an **automated robotic system** for dispensing and weighing powders into vials.  
It combines:  
- a **Mettler Toledo balance** (`WM` class)  
- a **UR3e robot** (`UR` class)  
- an **orchestrator** (`Sampler` class) to execute recipes defined in JSON  

The goal is to help chemists prepare vials efficiently and reproducibly.

---

## Table of Contents

1. [Overview](#overview)  
2. [Installation](#installation)  
3. [How to Run](#how-to-run)  
4. [Project Structure](#project-structure)  
5. [Functions & Status](#functions--status)  
6. [Roadmap](#roadmap)  
7. [License](#license)  

---

## Overview

### Global Workflow
1. The chemist defines a **recipe JSON file** containing:
   - the vials to prepare (slots)  
   - the powders to add, with target weights and tolerances  

2. The system executes the recipe:
   - **Balance (`WM`)**: door control, tare, zero, weight measurement, tolerance settings  
   - **Robot (`UR`)**: vial handling and powder manipulation  
   - **Sampler**: orchestrates the full workflow (JSON → execution → return of vials)  

3. Result: vials prepared automatically according to the given recipe.

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone <project_url>
   cd <project_folder>
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. Make sure that:
   - The **Mettler Toledo balance** is connected (serial port set correctly in `Class_WM.py`)  
   - The **UR robot** is reachable at the correct **IP address**  

---

## How to Run

### Running a recipe

The main script expects a JSON file describing vials and powders.  

Example:
```bash
python main.py recipe.json
```

### Example of `recipe.json`
```json
{
  "vials": [
    {
      "slot": 1,
      "materials": [
        {
          "name": "NaCl",
          "target_mg": 50,
          "tol_pct": 2
        },
        {
          "name": "KCl",
          "target_mg": 25,
          "tol_upper": 1,
          "tol_lower": 1,
          "tol_unit": "mg"
        }
      ]
    }
  ]
}
```

---

## Project Structure

```
AutomatedSampler/
├── Class_WM.py         # Balance interface (zero, tare, doors, weight, tolerances)
├── Class_UR.py         # UR robot interface (connect, run_program)
├── Class_Sampler.py    # Orchestrates recipes (JSON → execution)
├── main.py             # Entry point (loads recipe JSON and runs Sampler)
├── tests/              # Unit test scripts: testWM, testUR, ...
├── requirements.txt    # Python dependencies
└── README.md           # Documentation
```

---

## Functions & Status

👉 This table must be updated **manually** as you validate or fix functions.

| Class   | Function               | Description                                        | Status |
|---------|------------------------|----------------------------------------------------|--|
| WM      | `open_door()`          | Opens the balance doors                            | ⚠️ To test |
| WM      | `close_door()`         | Closes the balance doors                           | ⚠️ To test |
| WM      | `tare()`               | Tares the balance with the vial/powder inside      | ⚠️ To test |
| WM      | `zero()`               | Zeros the balance (no vial)                        | ⚠️ To test |
| WM      | `get_weight()`         | Returns the current measured weight                | ⚠️ To test |
| WM      | `set_target_weight()`  | Sets the target weight                             | ⚠️ To test |
| WM      | `set_tolerance_upper()`| Sets the upper tolerance                           | ⚠️ To test |
| WM      | `set_tolerance_lower()`| Sets the lower tolerance                           | ⚠️ To test |
| UR      | `connect()`            | Connects to the UR robot dashboard                 | ⚠️ To test |
| UR      | `disconnect()`         | Disconnects from the UR robot dashboard            | ⚠️ To test |
| UR      | `run_program()`        | Loads and runs a URP program                       | ⚠️ To test |
| Sampler | `load_recipe()`        | Loads a recipe from JSON                           | ⚠️ To test |
| Sampler | `execute()`            | Executes the full orchestration workflow           | ⚠️ To test |
| Sampler | `wait_for_continue()`  | Waits for manual user confirmation before resuming | ⚠️ To test |

*(Legend: ✅ working / ⚠️ needs testing / ❌ known bug)*

---

## Roadmap

- [ ] Check all functions
- [ ] Manage the Sampler Class to compute a recipe
- [ ] 

---

## License

This project is licensed under your choice (MIT, GPL, etc.).  
