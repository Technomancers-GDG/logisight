import { DriverLogin } from "../components/DriverLogin";

export function LoginPage({ onLogin, error, setError }) {
  return <DriverLogin onLogin={onLogin} error={error} setError={setError} />;
}
