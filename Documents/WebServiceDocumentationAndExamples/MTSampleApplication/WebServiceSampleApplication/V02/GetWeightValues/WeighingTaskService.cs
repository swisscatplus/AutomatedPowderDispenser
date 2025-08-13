//===========================================================================//
//                                     ___      _   ___          _           //
//   Mettler Toledo                   / _ \___ | | / (_)__  ____(_)          //
//                                   / // / _ `/ |/ / / _ \/ __/ /           //
//                                  /____/\_,_/|___/_/_//_/\__/_/            //
//                                                                           //
//===========================================================================//

namespace Weighing
{
    using MT.Laboratory.Balance.XprXsr.V02;
    using System.Linq;
    using WebServiceInfrastructure;

    public class WeighingTaskService
    {
        public static bool TryStartAutomatedDosingMethod(string sessionId, IWeighingTaskService weighingTaskService)
        {
            Logger.TraceNewLine("Start dosing automation method...");
            var listOfMethods = weighingTaskService.GetListOfMethods(new GetListOfMethodsRequest(sessionId));
            var automatedDosingMethod = listOfMethods.Methods.FirstOrDefault(m => m.MethodType == MethodType.AutomatedDosing);
            if (automatedDosingMethod == null)
            {
                Logger.TraceNewLine("No automated dosing method with type AutomatedDosing found (must be created manually on the terminal).");
                return false;
            }

            var response = weighingTaskService.StartTask(new StartTaskRequest(sessionId, automatedDosingMethod.Name));
            if (response.Outcome != Outcome.Success)
            {
                Logger.TraceNewLine("Automated dosing method could not be started.");
                return false;
            }

            return true;
        }
    }
}
