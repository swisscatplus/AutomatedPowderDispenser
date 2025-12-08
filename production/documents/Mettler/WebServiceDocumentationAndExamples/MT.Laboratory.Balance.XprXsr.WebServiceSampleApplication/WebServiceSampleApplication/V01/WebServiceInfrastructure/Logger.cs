namespace WebServiceInfrastructure
{
    using MT.Laboratory.Balance.XprXsr.V01;
    using System;

    public static class Logger
    {
        public static void TraceOutcome(Outcome outcome, string context, string error)
        {
            switch (outcome)
            {
                case Outcome.Success:
                    Console.WriteLine("{0} successful.", context);
                    break;
                case Outcome.Error:
                    Console.WriteLine("\nError on {0}: {1}.\n", context, error);
                    break;
                case Outcome.Canceled:
                    Console.WriteLine("\n{0} has been canceled..\n", context);
                    break;
                case Outcome.Timeout:
                    Console.WriteLine("\nTimeout on {0}.\n", context);
                    break;
            }
        }

        public static void Trace(string message, params object[] arg)
        {
            Console.WriteLine(message, arg);
        }

        public static void TraceNewLine(string message, params object[] arg)
        {
            Console.WriteLine(Environment.NewLine + message, arg);
        }

        public static void Finish()
        {
            // Wait for user to exit the application
            TraceNewLine("Press the Enter key to exit the application...");
            Console.ReadLine();
        }
    }
}
