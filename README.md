---
title: Guide -- Test bench XPR226Q + UR3e
---

Auteur : BEC Date : 28.11.2025 Version : 0.1

![](media/image1.jpeg){width="7.354166666666667in"
height="5.515625546806649in"}

# Table of contents {#table-of-contents .TOC-Heading}

[0. General infos [1](#_Toc215240344)](#_Toc215240344)

[0.1 Target audience [1](#target-audience)](#target-audience)

[0.2 Overview of the test bench
[1](#overview-of-the-test-bench)](#overview-of-the-test-bench)

[1 Introduction [2](#introduction)](#introduction)

[1.1 Global architecture
[2](#global-architecture)](#global-architecture)

[2 Quick start [3](#quick-start)](#quick-start)

[2.1 Launching app [3](#launching-app)](#launching-app)

[2.2 Example of complete cycle
[3](#example-of-complete-cycle)](#example-of-complete-cycle)

[3. Balance Mettler Toledo XPR226Q
[4](#in-mode-auto-steps-58-are-automatically-chained-for-a-single-powder.-multi-powder-recipes-are-handled-in-the-dedicated-mode-json-see-section-2.3.)](#in-mode-auto-steps-58-are-automatically-chained-for-a-single-powder.-multi-powder-recipes-are-handled-in-the-dedicated-mode-json-see-section-2.3.)

[3.1 Connexions & physical installation
[4](#connexions-physical-installation)](#connexions-physical-installation)

[3.2 Installation PC [4](#installation-pc)](#installation-pc)

[Refer the following link for documentation:
www.mt.com/global/en/home/library/technical-specifications/laboratory-weighing/web-service-how-to-guide.html 
In the folder of the projects you can find everything needed
C:\\XXX\\AutomatedPowderDispenser-main\\Documents\\Mettler
[4](#refer-the-following-link-for-documentation-www.mt.comglobalenhomelibrarytechnical-specificationslaboratory-weighingweb-service-how-to-guide.html-in-the-folder-of-the-projects-you-can-find-everything-needed-cxxxautomatedpowderdispenser-maindocumentsmettler)](#refer-the-following-link-for-documentation-www.mt.comglobalenhomelibrarytechnical-specificationslaboratory-weighingweb-service-how-to-guide.html-in-the-folder-of-the-projects-you-can-find-everything-needed-cxxxautomatedpowderdispenser-maindocumentsmettler)

[3.3 Integration in the GUI Tkinter
[4](#integration-in-the-gui-tkinter)](#integration-in-the-gui-tkinter)

[3.4 Troubleshooting balance
[4](#troubleshooting-balance)](#troubleshooting-balance)

[4. Bras robot UR3e [5](#bras-robot-ur3e)](#bras-robot-ur3e)

[4.1 Robot's role [5](#robots-role)](#robots-role)

[4.2 Connexion [5](#connexion)](#connexion)

[4.3 Communication robot ↔ PC
[5](#communication-robot-pc)](#communication-robot-pc)

[4.4 PC-side dependencies
[5](#pc-side-dependencies)](#pc-side-dependencies)

[4.5 Integration in the GUI Tkinter / scripts
[6](#integration-in-the-gui-tkinter-scripts)](#integration-in-the-gui-tkinter-scripts)

[4.6 Troubleshooting UR3e
[6](#troubleshooting-ur3e)](#troubleshooting-ur3e)

[5. Software of the test bench
[7](#software-of-the-test-bench)](#software-of-the-test-bench)

[5.1 Software architecture
[7](#software-architecture)](#software-architecture)

[5.2 Organisation du dossier soft
[8](#organisation-du-dossier-soft)](#organisation-du-dossier-soft)

[5.3 Main scripts [9](#main-scripts)](#main-scripts)

[5.4 Configuration files
[9](#configuration-files)](#configuration-files)

[8. Next steps [10](#next-steps)](#next-steps)

[8.1 Possible technical improvements
[10](#possible-technical-improvements)](#possible-technical-improvements)

[8.2 Ideas to extend the AutomatedPowderDispenser
[10](#ideas-to-extend-the-automatedpowderdispenser)](#ideas-to-extend-the-automatedpowderdispenser)

[8.3 Actual known limits
[11](#actual-known-limits)](#actual-known-limits)

[9. Version history [11](#version-history)](#version-history)

# General infos

## 0.1 Target audience

This document is intended for:

-   Process and development engineers working with the XPR226Q balance
    and the UR3e robot.

-   Laboratory staff operating the automated powder dispensing bench in
    day-to-day production or R&D.

-   Automation / software engineers who may need to maintain or extend
    the Python application.

The reader is expected to:

-   Know the basic safety rules of the UR3e collaborative robot and how
    to use the teach pendant at a high level.

-   Be familiar with the XPR226Q front panel (methods, draft shield,
    dosing module).

-   Have basic knowledge of Windows, Ethernet networking (IP addresses)
    and file paths.

-   For software maintenance: have basic knowledge of Python (functions,
    modules, virtual environments).

    2.  ## Overview of the test bench

The goal of this test bench is to automate small-quantity powder dosing
into vials using a Mettler Toledo XPR226Q balance (with Q3 dosing
module) and a UR3e robot arm.\
The robot moves vials and dosing heads between dedicated storage racks
and the balance, while a Python application coordinates all operations.

The main components are:

-   **Mettler Toledo XPR226Q** analytical balance with Q3 dosing module,
    controlled via Mettler Web Service over Ethernet.

-   **UR3e** 6-axis collaborative robot arm with a custom gripper.

-   **Vial storage** racks, with positions addressed in the GUI (E1-1,
    E1-2, ...).

-   **Dispenser storage** rack for powder dosing heads (RFID option
    available, not used yet in software).

-   **PC** (Windows) running a Python / Tkinter application ("Automated
    Powder Dispenser", APD).

-   **Ethernet switch** interconnecting PC, balance and UR3e on the same
    local network.

The Python GUI offers:

-   A **Manual mode** to control the balance and the robot independently
    (for debugging and manual operations).

-   An **Automatic mode** to run complete dosing cycles combining UR3e
    programs and XPR dosing jobs.

# Introduction

This document describes the automated powder dispensing test bench built
around a Mettler Toledo XPR226Q balance and a UR3e robot arm.\
Its objective is to provide:

-   A practical guide to start the bench and run a complete dosing
    cycle.

-   A high-level description of the hardware and software architecture.

-   Enough technical details so that another engineer can maintain or
    extend the system (e.g. add new vials, change IPs, adapt UR
    programs).

The bench was designed to:

-   Reduce manual handling of vials and dosing heads.

-   Improve repeatability of powder dosing sequences.

-   Serve as a platform for future automation (multi-powder recipes,
    traceability, etc.).

    1.  ## Global architecture

At a high level, the architecture is:

-   A **PC** runs the Python / Tkinter GUI.

-   The PC communicates with the **XPR226Q** via the Mettler Web Service
    over HTTP/HTTPS (SOAP), using the WSDL provided by Mettler.

-   The PC communicates with the **UR3e** using deviceRobotArm.py:

    -   The **Dashboard server** (TCP 29999) for high-level commands
        (power, load, play, stop, etc.).

    -   The **Script interface** (TCP 30002) for URScript streaming if
        needed.

    -   The **RTDE IO interface** for writing integers into input
        registers (GPii\[20\] / GPii\[21\]) used by UR programs.

    -   **SFTP** (SSH 22) to list and load .urp programs stored on the
        robot controller.

All three devices (PC, balance, UR3e) are connected to the same Ethernet
switch. The Python application acts as the single orchestrator: it
decides when to move vials and dispensers, when to close/open the
balance door, and when to start a dosing job.

# Quick start 

# 2.1 Launching app

**2.1 Launching the app**

1.  **Prepare the project folder**

    -   Copy the project directory (e.g. AutomatedPowderDispenser-main)
        onto the PC.

    -   In config.py, check and adapt:

        -   The paths under APP_CONFIG (base directory, soft, data, log,
            measures).

        -   The IP addresses of the balance and the UR3e in
            SCALE_CONFIG\[\"ip\"\] and UR3_CONFIG\[\"ip\"\].

        -   The WSDL path for the balance Web Service
            (SCALE_CONFIG\[\"wsdl_path\"\]).

2.  **Install Python and dependencies\
    **Make sure Python 3.x and the required Python packages are
    installed (see section 4.4 for details).

3.  **Start the GUI**

    -   Open a terminal / command prompt.

    -   Go to the soft directory:

    -   cd \<PROJECT_ROOT\>\\soft

    -   Launch the main GUI script main.py

    -   The main window opens with two tabs:

        -   **Mode Man** (manual mode).\
            Manual control of the balance and the UR3e for debugging,
            maintenance and test setups.

        -   **Mode Auto** (automatic sequence, work in progress).\
            Runs a fully automatic P1 → P2 → dosing job → P4 → P3 cycle
            for one vial and one powder, using the same safety checks as
            in manual mode.

        -   **Mode JSON** (multi-vial JSON recipe mode).\
            Executes a complete plan defined in a JSON file: for each
            vial, the application chains P1 → (P2 → dosing → P4) for
            each powder, then P3 to return the vial to storage.

    -   At the bottom of the window, the **Info** panel shows all logs
        (connections, errors, dosing events, UR3 states, etc.).

    2.  ## Example of ) complete cycle

A full dosing cycle typically follows these steps:

1.  **Check that the balance door is open.**\
    The application verifies the door position via the Web Service and
    opens the draft shield if needed.

2.  **Check that no vial is already on the pan.**\
    A quick weight acquisition is used to detect if the pan is empty.

3.  **Robot program P1 -- bring an empty vial to the balance.**\
    The UR3e takes an empty vial from the vial storage and places it
    onto the balance pan.

4.  **Close the balance door.**\
    The application closes the draft shield (required before starting a
    dosing job).

5.  **Check that the dispenser spot on the balance is empty.**\
    The system confirms that no dosing head is currently sitting on the
    "dispenser" position.

6.  **Robot program P2 -- bring the selected dispenser to the
    balance.**\
    The UR3e picks the powder dispenser from the dispenser storage and
    places it onto the balance.

7.  **Start a dosing job, then wait until it has finished.**\
    The application starts a Web Service "DosingAutomation" job with the
    chosen target and tolerances.\
    The balance automatically dispenses powder; when the job is
    finished, it sends notifications that are logged in the GUI (e.g.
    *"Job finished"*, *"End of DosingAutomation"*).\
    The automatic mode now uses these notifications to trigger the next
    UR3e program without any manual timing.

8.  **Robot program P4 -- bring back the dispenser to its storage
    position.**\
    Once the dosing job is finished and the door is open, the UR3e
    returns the dosing head to the dispenser storage.

9.  **Check that the door is open and that the vial is on the pan.**\
    Before removing the vial, the system ensures that the vial is still
    present and the draft shield is open.

10. **Robot program P3 -- bring the vial back to vial storage.**\
    The UR3e takes the vial from the pan and returns it to its storage
    position.

# In Mode Auto, steps 5--8 are automatically chained for a single powder. Multi-powder recipes are handled in the dedicated Mode JSON (see section 2.3).

## JSON-based automatic recipes (Mode JSON 

The JSON mode extends the basic automatic sequence to support multiple
vials and multiple powders per vial in a fully automatic way.

Instead of manually configuring each dosing job in the GUI, the operator
provides a JSON file describing the complete plan. A typical JSON file
looks like:

{

\"vials\": \[

{

\"vial_id\": \"E1-1\",

\"powders\": \[

{ \"name\": \"NAHCO3\", \"qty_mg\": 5.0 },

{ \"name\": \"NaCl\", \"qty_mg\": 3.0 }

\]

},

{

\"vial_id\": \"E1-2\",

\"powders\": \[

{ \"name\": \"KCl\", \"qty_mg\": 2.5 }

\]

}

\]

}

Each entry in \"vials\" defines:

• vial_id: the logical ID of the vial as used in the GUI (e.g.
\"E1-1\").

• powders: a list of powders, each with:

-- name: powder name, matching the dispenser label configured in
STORAGE_CONFIG.

-- qty_mg: target quantity in milligrams.

For each vial in the JSON plan, the application executes:

1\. Program P1 -- bring the vial to the balance.

The corresponding vial position is selected in the GUI, then P1 is
launched with the same pre-checks as in manual mode (door open, empty
pan, etc.).

2\. For each powder of this vial:

• Program P2 -- bring the corresponding dispenser to the balance.

The dispenser storage position is selected based on the powder name.

• Automatic dosing job.

The target weight and powder name are set from the JSON entry, then a
DosingAutomation job is started and monitored until completion.

• Program P4 -- return the dispenser to its storage position.

Once the dosing job is finished and the door is opened if needed, P4
brings the dispenser back to its rack.

3\. Program P3 -- return the vial to vial storage.

After all powders of the vial have been processed, P3 returns the vial
to its storage position.

The JSON mode loops over all vials defined in the file (P1 → (P2 +
dosing + P4) × N powders → P3) and stops automatically when the plan is
finished.

Any error (missing UR program, unknown vial ID or powder name,
connection loss) is reported in the Info log.

# 3. Balance Mettler Toledo XPR226Q

## 3.1 Connexions & physical installation

MT-SICS commands do not work with Q3 Dosing module or the XPR Automatic
Balance.\
So to control the operation of the Q3 dosing module remotely, we need to
use Web Service.\
So the Scale has to be linked via Ethernet through a switch to the PC.

## 3.2 Installation PC 

## Refer the following link for documentation: [www.mt.com/global/en/home/library/technical-specifications/laboratory-weighing/web-service-how-to-guide.html](http://www.mt.com/global/en/home/library/technical-specifications/laboratory-weighing/web-service-how-to-guide.html)   In the folder of the projects you can find everything needed C:\\XXX\\AutomatedPowderDispenser-main\\Documents\\Mettler

## 3.3 Integration in the GUI Tkinter 

See section 5.1 "Software architecture" for details about
deviceScale.py, deviceRobotArm.py and the GUI panels.

## 3.4 Troubleshooting balance

**Screen in sleep mode**\
If the balance screen is in sleep mode, some Web Service calls may fail
or time out. In that case:

-   Wake up the balance using the front panel.

-   Optionally call the "WakeupFromStandby" method from the PC
    application before starting a sequence.

**Web Service connection errors**

-   Check that the balance is powered on and connected to the same
    Ethernet switch as the PC.

-   Verify the IP address, port and WSDL path in SCALE_CONFIG in
    config.py.

-   If HTTPS is used, verify the certificate configuration (verify
    parameter).

**Method not found / protocol mismatch**

-   Ensure you are using the correct WSDL file version for the XPR226Q.

-   If the firmware of the balance has been updated, re-export the WSDL
    from Mettler's tools and update the path.

**Door / draft shield does not move**

-   Check the door_ids configuration in SCALE_CONFIG\[\"door_ids\"\].

-   Confirm that manual control from the front panel still works; if
    not, there might be a hardware issue

# 4. Bras robot UR3e

## 4.1 Robot's role

So far 4 main programs are implemented in the robot arm teach pendant :\
P1 taking vials to the scale\
P2 taking dispensers to the scale\
P3 bringing back vials from the scale\
P4 bringing back dispenser from the scale

## 4.2 Connexion

We connect the robot arm with ethernet threw a switch to the PC.

## 4.3 Communication robot ↔ PC

The python librairie ur_rtde is used

## 4.4 PC-side dependencies

On the PC, the UR3e integration requires the following software:

-   **Python 3.x** installed and available on the system PATH.

-   The **ur-rtde** Python package to access the RTDE IO interface and
    write into GPii registers.

-   The **paramiko** Python package to list .urp programs on the UR
    controller via SFTP (used for the program combobox).

-   Standard Python libraries (socket, threading, etc.) used in
    deviceRobotArm.py.

All the above can be installed in a virtual environment using pip, for
example:

pip install ur-rtde paramiko

The UR3e controller must have:

-   **Dashboard server** enabled.

-   **RTDE** enabled.

-   **SSH/SFTP** enabled (to allow program listing).

-   The correct IP address configured in the same subnet as the PC.

## 4.5 Integration in the GUI Tkinter / scripts

See section 5.1 "Software architecture" for details about
deviceScale.py, deviceRobotArm.py and the GUI panels.

## 4.6 Troubleshooting UR3e

If you have connection problems between the PC and the UR3e, check the
following:

-   **Network configuration**

    -   The robot and the PC must be on the same IP subnet (e.g.
        192.168.0.x).

    -   You must be able to ping the robot IP from the PC.

    -   The Ethernet cable and switch ports are correctly connected.

-   **Services enabled on the teach pendant**

    -   Dashboard server enabled.

    -   RTDE enabled.

    -   SSH/SFTP enabled (for program listing).

    -   No restrictive firewall or security setting blocking TCP ports
        22, 29999, 30002 and 30004.

![](media/image2.jpeg){width="1.831447944006999in"
height="3.248228346456693in"}![](media/image3.png){width="1.853611111111111in"
height="3.339102143482065in"}\
All services are enabled on the teach pendant SSH is enabled

![](media/image4.jpeg){width="2.021052055993001in"
height="3.555758967629046in"}

> Nothing is restricted

-   **Remote control mode**

    -   The robot must be in **Remote** control mode (not Local) for
        Dashboard commands such as play or load to be accepted.

    -   If the Dashboard reply mentions a safety lock or "not allowed
        due to safety", check the teach pendant safety messages.

-   **Program issues**

    -   The .urp program path loaded from the GUI must exist on the
        controller.

    -   If the program immediately returns to STOPPED, check the program
        on the pendant for runtime errors or missing waypoints.

    -   

# 5. Software of the test bench

![](media/image5.png){width="7.3447747156605425in"
height="6.167527340332459in"}

## 5.1 Software architecture

The software is organised in layers:

1.  **Configuration layer** -- config.py

    -   Central place for all configurable settings: paths (APP_CONFIG),
        balance Web Service parameters (SCALE_CONFIG), UR3 connection
        and mapping (UR3_CONFIG).

2.  **Device drivers**

    -   deviceScale.py: encapsulates all Web Service calls to the
        XPR226Q. It exposes high-level methods such as open_door(),
        close_door(), get_weight(), is_pan_empty(), start_dosing_job(),
        auto_confirm_dosing_notifications(), etc.

    -   deviceRobotArm.py: low-level client for the UR3e. It manages
        Dashboard, Script, RTDE IO and SFTP in a single class
        (\_UR3Client), and exposes a simpler façade class UR3 used by
        the GUI.

3.  **GUI panels (Tkinter)**

    -   winScale.py: graphical panel to control the balance (doors,
        zero/tare, read weight, start dosing job, monitor
        notifications).

    -   winRobotArm.py: graphical panel to control the UR3e (connect,
        power, brake, load/play/stop programs, select vials and storage
        positions).

    -   winVials.py & winStorage.py: small sub-windows to select vial
        and storage positions.

    -   winInfo.py: logging panel at the bottom of the main window, used
        by all modules to display messages to the user.

4.  **Application modes**

    -   winMan.py -- "Manual mode" tab.\
        Groups WinBalance (scale) and WinRobotArm (UR3) in a single view
        for manual operations and debugging.

    -   winAuto.py -- "Automatic mode" tab (single-cycle).\
        Runs a complete P1 → P2 → dosing job → P4 → P3 sequence for one
        vial and one powder.\
        This mode reuses the same safety checks as in manual mode (door
        and pan status, vial and storage selection) and automatically
        chains UR3 programs based on the robot program state and balance
        notifications.

    -   winJsonAuto.py -- "JSON mode" tab (multi-vial recipes).\
        Executes multi-vial, multi-powder plans loaded from a JSON
        file.\
        For each vial in the plan, the application chains:\
        P1 → (P2 → dosingAutomation → P4) for each powder → P3 at the
        end of the vial.\
        Callbacks are used to reuse the existing vial and storage
        selection logic from WinRobotArm and the dosing job
        configuration from WinBalance.

5.  **Main window**

    -   win.py: main entry point. It creates a WinMain Tk root, adds the
        two tabs (**Mode Man** and **Mode Auto**) and the bottom Info
        log. It also handles clean shutdown and device closing when the
        window is closed.

## 5.2 Organisation du dossier soft

The project is organised around config.py and the soft folder:

-   \<PROJECT_ROOT\>/config.py\
    Global configuration file for the whole application.

-   \<PROJECT_ROOT\>/soft/\
    Main Python source code:

    -   win.py -- main GUI entry point (Tk root, notebook tabs, layout).

    -   winMan.py -- Manual mode.

    -   winAuto.py -- Automatic mode.

    -   winScale.py -- Balance GUI.

    -   winRobotArm.py -- UR3e GUI.

    -   winJsonAuto.py -- JSON-based automatic mode (multi-vial
        recipes).

    -   winVials.py, winStorage.py -- vial and storage selection panels.

    -   winInfo.py -- logging window.

    -   deviceScale.py -- balance driver (Web Service).

    -   deviceRobotArm.py -- UR3e driver (Dashboard, Script, RTDE,
        SFTP).

    -   guiUtils.py -- shared helpers for Tkinter widgets (button
        factory, tooltips, etc.).

-   \<PROJECT_ROOT\>/data/

    -   Contains balance-related data (methods, templates, etc.).

    -   Measures/ subfolder (see APP_CONFIG\[\"measures_directory\"\])
        used to store measurement exports.

-   \<PROJECT_ROOT\>/log/

    -   Stores application log files (log_app_directory in APP_CONFIG).

    -   Log rotation and clean-up can be configured through config.py.

## 5.3 Main scripts

-   **win.py**\
    Entry point of the GUI. Creates the main window (WinMain),
    initialises the info log panel, and adds the two tabs:

    -   WinMan (manual mode).

    -   WinAuto (automatic mode).

    -   WinJsonAuto (JSON-based multi-vial automatic mode)

-   **winMan.py**\
    Hosts WinBalance and WinRobotArm side by side. It is the main place
    to:

    -   Connect / disconnect the balance and the robot.

    -   Manually test UR programs (P1--P4).

    -   Manually start a dosing job and observe the raw notifications
        from the scale.

-   **winAuto.py**\
    Implements high-level automatic sequences. For example:\
    P1 → P2 → dosing job → P3 → P4, including pre-checks (empty pan,
    selected vial, selected storage, dosing head present, etc.).

-   **winScale.py**\
    User interface around deviceScale.WM:

    -   Connect / disconnect Web Service.

    -   Open / close door.

    -   Zero / tare / read weight.

    -   Start a dosing job and spawn a background thread to auto-confirm
        dosing notifications and log each step.

-   **winRobotArm.py**\
    User interface around deviceRobotArm.UR3:

    -   Configure IP and ports.

    -   Connect / disconnect.

    -   Power on/off and brake release.

    -   Refresh robot and safety modes.

    -   List .urp files via SFTP and load them.

    -   Launch a programme with the correct RTDE integer register set
        for vial / dispenser indices.

-   **deviceScale.py / deviceRobotArm.py**\
    Abstract all hardware communication details so the GUI code stays
    concise and readable.

-   **winJsonAuto.py**\
    Implements the JSON-based automatic mode.\
    It loads a JSON file describing a list of vials and powders (see
    section 2.3), then orchestrates:\
    P1 to bring each vial to the balance,\
    P2 + dosingAutomation + P4 for each powder of the vial,\
    and finally P3 to return the vial to storage.\
    All safety checks (door position, pan content, selected vial and
    storage) are delegated to the same helpers used in manual mode.

## 5.4 Configuration files

The main configuration file is config.py.\
It centralises all important settings so that changing the bench
configuration usually only requires editing this single file.

Key setions:

-   **APP_CONFIG**

    -   Base directory of the project.

    -   Paths to the soft, data, log and Measures folders.

    -   Log rotation and clean-up parameters.

-   **SCALE_CONFIG**

    -   IP, port, scheme (http / https) and WSDL path for the XPR226Q
        Web Service.

    -   Password used to decrypt the SessionId.

    -   Door identifiers and open/close widths for the draft shield.

    -   Timeouts and autoconnect behaviour.

-   **UR3_CONFIG**

    -   IP and ports for Script and Dashboard servers.

    -   SFTP credentials and program directory on the UR controller.

    -   RTDE input register index used for vial / dispenser numbers.

    -   Mapping from GUI vial IDs (e.g. \"E1-1\") to integer indices
        used in UR programs (vial_id_to_number).

Any change of network, directory structure, or UR program mapping should
first be reflected in config.py.

# 8. Next steps

## 8.1 Possible technical improvements

 Extend the existing detection of dosing job completion:\
The application already uses "Job finished" and "End of
DosingAutomation" notifications to automatically trigger the next UR3
program in automatic modes.

Future work could extend this to more complex recipes (conditional
steps, automatic retries, error handling policies).

 Improve **error handling and retries** on both channels (balance Web
Service and UR3 Dashboard).

 Add a **status bar** in the GUI summarising: balance connection, UR3
connection, current program, and dosing job status.

 Provide a simple **"recipe editor"** to pre-define multi-powder
dispensing steps, instead of manually setting each dosing job.

 Provide a simple **"recipe editor"** to pre-define multi-powder
dispensing steps, instead of manually setting each dosing job.

## 8.2 Ideas to extend the AutomatedPowderDispenser

• **Automatic vial presence detection** in the storage:

-   Use a camera and computer vision to detect which positions in the
    vial rack are occupied.

-   Automatically update the vial selection UI based on actual
    occupancy.

• **Dispenser identification in storage**:

-   Since the dispenser rack already has an RFID module, extend the
    system to read dispenser IDs when a dosing head is placed back.

-   Maintain a live mapping between physical positions and dispenser
    labels.

• **Automatic vial closing after dosing**:

-   Add a mechanical station (or a robot tool) to close vials once they
    are filled to avoid contamination and losses.

• **Traceability / logging per sample**:

-   Generate a report for each vial: powders used, target masses, final
    net mass, timestamps, errors, etc.

## 8.3 Actual known limits

 The tolerances profile of the XPR226Q is not fully exploited yet. For
now, the application mostly checks if the final weight is within fixed
tolerances, but the balance could enforce tolerances and acceptance
criteria more intelligently.

 The current automatic mode still relies on a relatively simple
chaining logic between UR3 programs and dosing jobs. Complex recipes
(many powders, conditionals, re-tries) are not yet supported.

 Vial and dispenser storage positions are configured manually; there is
no closed-loop verification of what is really in each position.

# 9. Version history

  --------- ------------ -------------------- ------------------------------
  Version   Date         Auteur               Modifications

  1.0       27.11.2025   Eshaya-Chauvin       Initial version
                         Bastien              

  1.1       28.11.2025   Eshaya-Chauvin       Added JSON-based automatic
                         Bastien              mode, updated automatic
                                              chaining between UR3 programs
                                              and dosing jobs, and
                                              documented the JSON recipe
                                              workflow.
  --------- ------------ -------------------- ------------------------------
