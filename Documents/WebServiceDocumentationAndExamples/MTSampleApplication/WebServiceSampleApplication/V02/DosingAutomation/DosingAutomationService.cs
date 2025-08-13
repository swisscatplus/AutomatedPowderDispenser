//===========================================================================//
//                                     ___      _   ___          _           //
//   Mettler Toledo                   / _ \___ | | / (_)__  ____(_)          //
//                                   / // / _ `/ |/ / / _ \/ __/ /           //
//                                  /____/\_,_/|___/_/_//_/\__/_/            //
//                                                                           //
//===========================================================================//

namespace DosingAutomation
{
    using MT.Laboratory.Balance.XprXsr.V02;
    using System;
    using System.Linq;
    using System.Threading;
    using WebServiceInfrastructure;

    public class DosingAutomationService
    {
        public static bool StartJobList(string sessionId, DosingJob[] dosingJobs, IDosingAutomationService dosingAutomationClient)
        {
            Logger.TraceNewLine("Starting dosing job list...");
            var startJobListRequest = new StartExecuteDosingJobListAsyncRequest(sessionId, dosingJobs);
            var response = dosingAutomationClient.StartExecuteDosingJobListAsync(startJobListRequest);
            Logger.TraceOutcome(response.Outcome, "StartDosingJobList", response.ErrorMessage);
            if (response.Outcome != Outcome.Success)
            {
                if (response.JobErrors != null)
                {
                    foreach (var responseJobError in response.JobErrors)
                    {
                        Logger.Trace("DosingJob validation error: " + responseJobError.Error);
                    }
                }

                return false;
            }

            return true;
        }

        public static void StartHandlingDosingAutomationNotifications(string sessionId, NotificationServiceClient notificationClient, DosingAutomationServiceClient dosingAutomationClient)
        {
            Logger.TraceNewLine("Starting handling dosing automation notifications...");
            var pollingCount = 0;
            while (true)
            {
                var response = notificationClient.GetNotifications(new GetNotificationsRequest(sessionId, 500));
                if (pollingCount > 200 || response.Notifications.Any(n => n is DosingAutomationFinishedAsyncNotification))
                {
                    Logger.Trace("> Stop checking for notifications.");
                    // stop polling
                    return;
                }

                Logger.Trace("> Checking for notifications...");

                foreach (var notificationNotification in response.Notifications)
                {
                    var actionNotification = notificationNotification as DosingAutomationActionAsyncNotification;
                    if (actionNotification != null)
                    {
                        HandleActionRequest(actionNotification.DosingJobActionType, actionNotification.ActionItem, sessionId, dosingAutomationClient);
                    }

                    var jobFinished = notificationNotification as DosingAutomationJobFinishedAsyncNotification;
                    if (jobFinished != null)
                    {
                        if (jobFinished.Outcome == Outcome.Success)
                        {
                            Logger.Trace("DosingJob result: Dosing job success (duration {0}s).", jobFinished.DosingResult.DurationInSeconds);
                        }
                        else
                        {
                            Logger.Trace("DosingJob result: Dosing job failure: {0}.", jobFinished.DosingError);
                        }
                    }

                    var dosingAutomationFinished = notificationNotification as DosingAutomationFinishedAsyncNotification;
                    if (dosingAutomationFinished != null)
                    {
                        Logger.Trace("DosingAutomationFinished result: " + dosingAutomationFinished.FailureReason);
                    }
                }

                Thread.Sleep(800);
                pollingCount++;
            }
        }

        private static void HandleActionRequest(DosingJobActionType actionType, string actionItem, string sessionId, DosingAutomationServiceClient dosingAutomationClient)
        {
            Logger.Trace("Executing action: {0} '{1}'...", actionType, actionItem);

            // simulate a realistic action execution
            Thread.Sleep(2000);

            switch (actionType)
            {
                case DosingJobActionType.PlaceDosingHead:
                    dosingAutomationClient.ConfirmDosingJobAction(new ConfirmDosingJobActionRequest(sessionId, DosingJobActionType.PlaceDosingHead, actionItem));
                    break;
                case DosingJobActionType.RemoveDosingHead:
                    dosingAutomationClient.ConfirmDosingJobAction(new ConfirmDosingJobActionRequest(sessionId, DosingJobActionType.RemoveDosingHead, actionItem));
                    break;
                case DosingJobActionType.PlaceVial:
                    dosingAutomationClient.ConfirmDosingJobAction(new ConfirmDosingJobActionRequest(sessionId, DosingJobActionType.PlaceVial, actionItem));
                    break;
                case DosingJobActionType.RemoveVial:
                    dosingAutomationClient.ConfirmDosingJobAction(new ConfirmDosingJobActionRequest(sessionId, DosingJobActionType.RemoveVial, actionItem));
                    break;
                default:
                    throw new ArgumentOutOfRangeException(nameof(actionType), actionType, null);
            }

            Logger.Trace("Action confirmed.");
        }
    }
}
