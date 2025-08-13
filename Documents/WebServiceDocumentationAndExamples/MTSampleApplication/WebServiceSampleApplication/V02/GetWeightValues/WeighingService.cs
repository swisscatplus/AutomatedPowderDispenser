namespace Weighing
{
    using MT.Laboratory.Balance.XprXsr.V02;
    using WebServiceInfrastructure;

    public class WeighingService
    {
        public static bool Zero(string sessionId, IWeighingService weighingService)
        {
            //Zeroing
            Logger.Trace("Zeroing");
            var zeroRequest = new ZeroRequest
            {
                SessionId = sessionId
            };
            var zeroResponse = weighingService.Zero(zeroRequest);
            Logger.TraceOutcome(zeroResponse.Outcome, "Zero", zeroResponse.ErrorMessage);

            return zeroResponse.Outcome == Outcome.Success;
        }

        public static void GetWeightValues(string sessionId, IWeighingService weighingService, IWeighingTaskService weighingTaskService)
        {
            // start method "General weighing"
            Logger.Trace("Starting task");
            var startTaskResult = weighingTaskService.StartTask(new StartTaskRequest
            {
                SessionId = sessionId,
                MethodName = "General Weighing"
            }
            );

            if (startTaskResult.Outcome != Outcome.Success)
            {
                Logger.Trace("Could not start task.");
            }

            //set target and tolerances
            Logger.Trace("Setting task and tolerances");
            var setTTkResponse = weighingTaskService.SetTargetValueAndTolerances(new SetTargetValueAndTolerancesRequest
            {
                SessionId = sessionId,
                LowerTolerance = new WeightWithUnit { Value = 1, Unit = Unit.Gram },
                TargetWeight = new WeightWithUnit { Value = 5, Unit = Unit.Gram },
                UpperTolerance = new WeightWithUnit { Value = 1, Unit = Unit.Gram }
            });
            Logger.TraceOutcome(setTTkResponse.Outcome, "Setting target and tolerances", setTTkResponse.ErrorMessage);

            //Zeroing
            Logger.Trace("Zeroing");
            var zeroRequest = new ZeroRequest
            {
                SessionId = sessionId
            };
            var zeroResponse = weighingService.Zero(zeroRequest);
            Logger.TraceOutcome(zeroResponse.Outcome, "Zero", zeroResponse.ErrorMessage);

            //Add to protocol
            Logger.Trace("Adding result to protocol.");
            var result = weighingTaskService.AddToProtocol(new AddToProtocolRequest
            {
                SessionId = sessionId
            });

            if (result.WeighingItem != null)
            {
                Logger.Trace("The weight value is: {0} {1}, Alibi ID: {2}\n",
                    result.WeighingItem.WeightSample.NetWeight.Value, result.WeighingItem.WeightSample.NetWeight.Unit, result.WeighingItem.AlibiId);
            }

            //Complete the Task
            Logger.Trace("Completing the task.");
            var completeTaskResponse = weighingTaskService.CompleteCurrentTask(new CompleteCurrentTaskRequest
            {
                SessionId = sessionId
            });
            Logger.TraceOutcome(completeTaskResponse.Outcome, "Complete task", completeTaskResponse.ErrorMessage);
        }
    }
}