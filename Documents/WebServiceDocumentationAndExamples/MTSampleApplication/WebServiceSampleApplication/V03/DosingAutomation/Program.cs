//===========================================================================//
//                                     ___      _   ___          _           //
//   Mettler Toledo                   / _ \___ | | / (_)__  ____(_)          //
//                                   / // / _ `/ |/ / / _ \/ __/ /           //
//                                  /____/\_,_/|___/_/_//_/\__/_/            //
//                                                                           //
//===========================================================================//

namespace DosingAutomation
{
    using MT.Laboratory.Balance.XprXsr.V03;
    using System.Collections.Generic;
    using System.Linq;
    using WebServiceInfrastructure;
    using WebServiceInfrastructure.Configuration;
    using Weighing;

    class Program
    {
        static void Main()
        {
            StartDosingAutomationSample();
        }

        private static void StartDosingAutomationSample()
        {
            // configure ip/password inside the web config helper class
            var webConfig = WebConfigHelper.CreateWebConfig();

            // init service clients
            var notificationClient = webConfig.CreateClient<NotificationServiceClient>();
            var dosingAutomationClient = webConfig.CreateClient<DosingAutomationServiceClient>();
            var weighingClient = webConfig.CreateClient<WeighingServiceClient>();
            var weighingTaskClient = webConfig.CreateClient<WeighingTaskServiceClient>();

            using (var session = new Session(webConfig))
            {
                // zero 
                if (WeighingService.Zero(session.SessionId, weighingClient))
                {
                    // start automated dosing method if existing on terminal
                    if (WeighingTaskService.TryStartAutomatedDosingMethod(session.SessionId, weighingTaskClient))
                    {
                        // start job list
                        var demoDosingJobList = CreateDosingJobList().ToArray();
                        if (DosingAutomationService.StartJobList(session.SessionId, demoDosingJobList, dosingAutomationClient))
                        {
                            // start dosing automation interaction
                            DosingAutomationService.StartHandlingDosingAutomationNotifications(session.SessionId, notificationClient, dosingAutomationClient);
                        }
                    }
                }

                // notify user
                Logger.Finish();
            }
        }

        private static IEnumerable<DosingJob> CreateDosingJobList()
        {
            yield return new DosingJob
            {
                SubstanceName = "Sugar",
                VialName = "Vial1",
                TargetWeight = new WeightWithUnit { Unit = Unit.Milligram, Value = 221 }
            };

            yield return new DosingJob
            {
                SubstanceName = "Sugar",
                VialName = "Vial2",
                TargetWeight = new WeightWithUnit { Unit = Unit.Milligram, Value = 22 }
            };
        }
    }
}
